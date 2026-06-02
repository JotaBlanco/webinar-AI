"""Physics primitives shared by the five prefilled candidate models.

Everything that's tedious-but-orthogonal-to-the-physics-hypothesis lives
here: RK4 integration, slip-angle equations, the Fiala tire curve,
quasi-static lateral load transfer, the friction-circle envelope, and a
relaxation-length first-order tire filter.

The five `phases/3-implement/models/m*/model.py` files import from here.
A bug fixed once lands in five places.

Conventions
-----------
- Angles in radians, speeds in m/s, forces in N, mass in kg.
- Sign convention: yaw rate ψ̇ positive counter-clockwise (left turn).
  This matches the truth column `yaw_rate_meas_rads` in the dataset.
- All ODE state vectors are numpy arrays, RK4 is the integrator by default.
- At very low `v_mps` (under 1.5 m/s) every dynamic model degenerates into
  passthrough of `yaw_rate_pred_rads` (V0). The harness builds in the
  guard; do not rewrite it in each model.
"""
from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------------------
# Platform priors — initial guesses for fitting. NOT gospel.
# ---------------------------------------------------------------------------
# F150 and Mach-E come straight from openpilot carParams (see
# code/parameters.py). Tesla is included for parity but has no truth.
# Hyundai Ioniq 5 is not in carParams; values below are public-spec
# estimates (mass from Hyundai datasheet, I_z scaled from Tesla's
# m·L²/12 ratio, C_α midway between Tesla and Mach-E). Agents are
# expected to fit C_αf, C_αr, I_z on Ioniq.

VEHICLE_PRIORS: dict[str, dict[str, float]] = {
    "FORD_F_150_LIGHTNING_MK1": {
        "m":         3084.0,    # kg
        "I_z":       9903.37,   # kg·m²
        "l_f":       1.628,     # m, CG-to-front
        "l_r":       2.072,     # m, CG-to-rear
        "L":         3.700,     # m, wheelbase
        "C_alpha_f": 378_307.0, # N/rad
        "C_alpha_r": 469_878.0, # N/rad
        "h_cg":      0.74,      # m, CG height (truck, high)
        "t_w":       1.71,      # m, track width
        "mu":        0.95,      # tire-road friction (dry asphalt, OE)
        "g":         9.81,
    },
    "FORD_MUSTANG_MACH_E_MK1": {
        "m":         2336.0,
        "I_z":       4879.05,
        "l_f":       1.313,
        "l_r":       1.671,
        "L":         2.984,
        "C_alpha_f": 286_551.0,
        "C_alpha_r": 355_912.0,
        "h_cg":      0.55,
        "t_w":       1.62,
        "mu":        1.00,
        "g":         9.81,
    },
    "HYUNDAI_IONIQ_5": {
        # Public-spec estimates — fit these on data.
        "m":         2100.0,
        "I_z":       4000.0,
        "l_f":       1.460,
        "l_r":       1.540,
        "L":         3.000,
        "C_alpha_f": 240_000.0,
        "C_alpha_r": 360_000.0,
        "h_cg":      0.58,
        "t_w":       1.63,
        "mu":        1.00,
        "g":         9.81,
    },
    "TESLA_MODEL_3": {
        # No truth — these are reference values for symmetric API.
        "m":         2035.0,
        "I_z":       3945.5,
        "l_f":       1.4375,
        "l_r":       1.4375,
        "L":         2.875,
        "C_alpha_f": 222_882.0,
        "C_alpha_r": 352_332.0,
        "h_cg":      0.50,
        "t_w":       1.58,
        "mu":        1.00,
        "g":         9.81,
    },
}

V_MIN_DYNAMIC = 4.0   # m/s — below this, passthrough V0.
                      # The linearised dynamic single-track has a 1/v term in
                      # the slip-angle equations; for stiff vehicles (F150's
                      # C_α ≈ 4e5 N/rad) the system becomes ill-conditioned
                      # under RK4 at the sim.csv 50 Hz rate when v drops
                      # below ~3 m/s. 4 m/s is conservative and the kinematic
                      # V0 is perfectly accurate at parking-lot speeds anyway.
                      # Models that don't share this 1/v issue (e.g. M4's
                      # algebraic relaxation-length filter) can pass a smaller
                      # floor explicitly.
DT_FALLBACK   = 0.01  # s    — guard against zero/negative dt


def prior(platform: str) -> dict[str, float]:
    """Return a fresh copy of the vehicle prior dict for `platform`."""
    if platform not in VEHICLE_PRIORS:
        raise KeyError(f"No vehicle prior for {platform!r}")
    return dict(VEHICLE_PRIORS[platform])


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------

def rk4_step(f, state: np.ndarray, dt: float, *args) -> np.ndarray:
    """One RK4 step of `state_dot = f(state, *args)`. `args` is forwarded.

    Use this for any 2- or 4-state ODE. For an ODE that depends on per-step
    inputs (δ, v, a_long), wrap them in *args and reference inside `f`.
    """
    k1 = f(state, *args)
    k2 = f(state + 0.5 * dt * k1, *args)
    k3 = f(state + 0.5 * dt * k2, *args)
    k4 = f(state + dt * k3, *args)
    return state + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


def safe_dt(t: np.ndarray) -> np.ndarray:
    """Return per-row dt with no zeros/negatives. Index-aligned with `t`."""
    dt = np.diff(t, prepend=t[0])
    dt[dt <= 0] = DT_FALLBACK
    return dt


# ---------------------------------------------------------------------------
# Slip angles (linear, small-angle)
# ---------------------------------------------------------------------------

def slip_angles_linear(
    beta: float, psi_dot: float, delta: float, v: float,
    l_f: float, l_r: float,
) -> tuple[float, float]:
    """Linearised front / rear slip angles at the tire patches.

    Conventional automotive sign: α positive = slip outward (front
    pushed left in a right turn means α_f > 0 with δ > 0). For the
    linearised single-track:

        α_f = β + l_f · ψ̇ / v − δ
        α_r = β − l_r · ψ̇ / v

    All inputs scalar. `v` should already be clamped ≥ V_MIN_DYNAMIC.
    """
    inv_v = 1.0 / max(v, V_MIN_DYNAMIC)
    alpha_f = beta + l_f * psi_dot * inv_v - delta
    alpha_r = beta - l_r * psi_dot * inv_v
    return alpha_f, alpha_r


# ---------------------------------------------------------------------------
# Tire force models
# ---------------------------------------------------------------------------

def fy_linear(alpha: float, C_alpha: float) -> float:
    """F_y = -C_α · α. Sign: F_y opposes α."""
    return -C_alpha * alpha


def fy_fiala(alpha: float, C_alpha: float, mu: float, F_z: float) -> float:
    """Fiala piecewise-linear-to-saturation tire force.

    α_sl = atan(3 μ F_z / C_α)        full saturation slip
    F_y  = -C_α tan(α)   if |α| < α_sl
         = -sign(α) · μ F_z otherwise

    Reduces to linear tire when |α| is small (tan ≈ α).
    """
    if F_z <= 0 or mu <= 0:
        return 0.0
    alpha_sl = np.arctan(3.0 * mu * F_z / C_alpha)
    if abs(alpha) < alpha_sl:
        return -C_alpha * np.tan(alpha)
    return -np.sign(alpha) * mu * F_z


# ---------------------------------------------------------------------------
# Quasi-static lateral load transfer
# ---------------------------------------------------------------------------

def axle_load_static(m: float, l_f: float, l_r: float, g: float) -> tuple[float, float]:
    """Static normal load on front and rear axle (total, both wheels)."""
    L = l_f + l_r
    F_z_front = m * g * l_r / L
    F_z_rear  = m * g * l_f / L
    return F_z_front, F_z_rear


def lateral_load_transfer(
    F_z_axle: float, a_y: float, h_cg: float, t_w: float, g: float,
) -> tuple[float, float]:
    """Steady lateral load transfer per axle.

    Returns (F_z_inner, F_z_outer) — wheel normal loads at this axle.
    The transfer magnitude is `ΔF_z = m_axle · a_y · h_cg / t_w` per
    axle (approximate; full ride-height-coupled formulation requires
    suspension states we don't have).

    Sign: a_y > 0 means CG accelerates left → right wheels become outer
    and gain load.
    """
    m_axle = F_z_axle / g
    delta_Fz = m_axle * a_y * h_cg / t_w
    F_z_left  = 0.5 * F_z_axle - delta_Fz
    F_z_right = 0.5 * F_z_axle + delta_Fz
    F_z_left  = max(F_z_left,  0.0)
    F_z_right = max(F_z_right, 0.0)
    return F_z_left, F_z_right


# ---------------------------------------------------------------------------
# Friction circle
# ---------------------------------------------------------------------------

def friction_circle_cap(F_y_demand: float, F_x: float, mu: float, F_z: float) -> float:
    """Cap requested lateral force to what's left after longitudinal demand.

    Available lateral capacity:
        F_y_max = sqrt((μ F_z)² - F_x²),  zero if F_x exceeds μF_z.

    Sign of `F_y_demand` preserved.
    """
    F_total_max = mu * F_z
    if abs(F_x) >= F_total_max:
        return 0.0
    F_y_max = np.sqrt(F_total_max * F_total_max - F_x * F_x)
    if abs(F_y_demand) <= F_y_max:
        return F_y_demand
    return np.sign(F_y_demand) * F_y_max


# ---------------------------------------------------------------------------
# Relaxation-length (first-order tire filter in *distance*)
# ---------------------------------------------------------------------------

def relax_step(F_y_state: float, F_y_demand: float, v: float, sigma: float, dt: float) -> float:
    """First-order relaxation in distance: dF_y/dt = (v/σ)·(F_y_demand − F_y).

    `sigma` is the relaxation length (m). At v = 0 the state freezes.
    Reduces to identity (F_y_demand) as σ → 0.
    """
    if sigma <= 0.0 or v <= V_MIN_DYNAMIC:
        return F_y_demand
    alpha = 1.0 - np.exp(-v * dt / sigma)
    return F_y_state + alpha * (F_y_demand - F_y_state)


# ---------------------------------------------------------------------------
# V0 passthrough fallback
# ---------------------------------------------------------------------------

def v0_passthrough(yaw_rate_pred_rads: np.ndarray) -> np.ndarray:
    """Honest fallback when a dynamic model degenerates (low v, no truth)."""
    return np.asarray(yaw_rate_pred_rads, dtype=float).copy()
