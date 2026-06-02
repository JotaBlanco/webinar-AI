"""Shared helpers for every physics-catalog model.

Three responsibilities:
  1. **Per-platform vehicle parameters** — mass / wheelbase / CG split / Iz priors,
     keyed by platform. Catalogue models override the rows they actually fit.
  2. **State-space integrators** — RK4 stepper for the linear and nonlinear
     dynamic single-track. Each model imports the stepper it needs and supplies
     its own tyre-force function.
  3. **Route-grouped fitter** — `fit_with_route_cv()` takes a predict-factory
     callable + an init/bounds spec, fits via scipy `minimize` against pooled
     dev yaw RMSE, and computes route-grouped CV σ that gets written into
     `coeffs.json` (so the bias_without_route_cv gate passes for any model
     that does fit a per-platform bias term).

Numerical stability notes
-------------------------
- Below `V_FLOOR_MPS = 2.0` the dynamic equations are ill-conditioned (the
  1/v term in the slip-angle formula blows up). All catalogue models fall
  through to V0 passthrough in this regime.
- RK4 is used everywhere; `step_rk4` and `step_rk4_with_tyre` differ only in
  which tyre-force function they call.
- The integrator does *not* attempt sub-stepping. dt in the dataset is ~0.01s
  which is comfortably inside RK4's stability radius for these dynamics.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Per-platform physical parameters (priors; the fitter overrides what it tunes)
# ---------------------------------------------------------------------------
#
# Values are textbook order-of-magnitude estimates for these specific vehicle
# classes. They are NOT calibration outputs. Catalogue model defaults inherit
# these and each model's fit.py refits the subset it cares about against the
# project's dev split via route-grouped CV.

PLATFORM_PRIORS: dict[str, dict[str, float]] = {
    "FORD_MUSTANG_MACH_E_MK1": {
        "m":          2200.0,    # kg
        "L":          2.984,     # m  — wheelbase
        "lf":         1.30,      # m  — CG to front axle
        "lr":         1.684,     # m  — CG to rear axle (= L - lf)
        "Iz":         3200.0,    # kg·m² — yaw moment of inertia (FIT)
        "C_alpha_f":  90000.0,   # N/rad — front linearised cornering stiffness (FIT)
        "C_alpha_r": 110000.0,   # N/rad — rear cornering stiffness (FIT)
        "h_cg":       0.55,      # m  — CG height (relevant for dst_load only)
    },
    "FORD_F_150_LIGHTNING_MK1": {
        "m":          3200.0,    # heavy electric truck
        "L":          3.700,
        "lf":         1.85,
        "lr":         1.85,
        "Iz":         6000.0,
        "C_alpha_f": 160000.0,
        "C_alpha_r": 190000.0,
        "h_cg":       0.85,
    },
    "HYUNDAI_IONIQ_5": {
        "m":          2100.0,
        "L":          3.000,
        "lf":         1.45,
        "lr":         1.55,
        "Iz":         3000.0,
        "C_alpha_f":  85000.0,
        "C_alpha_r": 100000.0,
        "h_cg":       0.55,
    },
    "TESLA_MODEL_3": {  # no truth; passthrough
        "m":          1850.0,
        "L":          2.875,
        "lf":         1.40,
        "lr":         1.475,
        "Iz":         2800.0,
        "C_alpha_f":  85000.0,
        "C_alpha_r": 110000.0,
        "h_cg":       0.50,
    },
}

# Platforms that have no truth channel in their sim.csv. All catalogue models
# fall through to V0 passthrough on these.
PASSTHROUGH_PLATFORMS: tuple[str, ...] = ("TESLA_MODEL_3",)

GRAVITY = 9.81
V_FLOOR_MPS = 2.0           # below this, fall through to V0 passthrough
DEFAULT_DT_S = 0.01         # used only if the time-step in the data is missing


# ---------------------------------------------------------------------------
# RK4 steppers — generic over the tyre-force function
# ---------------------------------------------------------------------------

def step_rk4_linear(state: np.ndarray, delta: float, v: float, p: dict, dt: float) -> np.ndarray:
    """One RK4 step of the LINEAR dynamic single-track.

    State: [beta, psi_dot] — sideslip @ CG (rad), yaw rate (rad/s).
    Input: delta = road wheel angle (rad), v = speed (m/s).
    Linear tyre: F_y = -C_alpha * alpha.
    """
    Cf, Cr = p["C_alpha_f"], p["C_alpha_r"]

    def f(s):
        beta, psi_dot = s
        if v < 1e-3:
            return np.zeros(2)
        alpha_f = beta + p["lf"] * psi_dot / v - delta
        alpha_r = beta - p["lr"] * psi_dot / v
        Fyf = -Cf * alpha_f
        Fyr = -Cr * alpha_r
        beta_dot = (Fyf + Fyr) / (p["m"] * v) - psi_dot
        psidd    = (p["lf"] * Fyf - p["lr"] * Fyr) / p["Iz"]
        return np.array([beta_dot, psidd])

    k1 = f(state)
    k2 = f(state + 0.5 * dt * k1)
    k3 = f(state + 0.5 * dt * k2)
    k4 = f(state + dt * k3)
    return state + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)


def step_rk4_tyre(
    state: np.ndarray,
    delta: float,
    v: float,
    p: dict,
    dt: float,
    tyre_fn: Callable[[float, float, dict, str], float],
) -> np.ndarray:
    """RK4 step with a caller-supplied tyre force function `tyre_fn(alpha, Fz, p, which)`.

    `which` is `"front"` or `"rear"`. Per-axle normal load `Fz` is computed inside
    here from p["m"], p["lf"], p["lr"], and optionally p["a_long_mps2"] / p["h_cg"]
    if longitudinal load transfer is enabled (dst_load model).
    """
    a_long = p.get("a_long_mps2", 0.0)
    h_cg   = p.get("h_cg", 0.0)
    L = p["L"]; m = p["m"]; lf = p["lf"]; lr = p["lr"]
    # Static + dynamic axle loads (positive a_long = accel → load shifts rearward).
    Fz_f_static = m * GRAVITY * lr / L
    Fz_r_static = m * GRAVITY * lf / L
    dFz = m * a_long * h_cg / L   # transferred from front to rear under acceleration
    Fz_f = max(Fz_f_static - dFz, 100.0)
    Fz_r = max(Fz_r_static + dFz, 100.0)

    def f(s):
        beta, psi_dot = s
        if v < 1e-3:
            return np.zeros(2)
        alpha_f = beta + lf * psi_dot / v - delta
        alpha_r = beta - lr * psi_dot / v
        Fyf = tyre_fn(alpha_f, Fz_f, p, "front")
        Fyr = tyre_fn(alpha_r, Fz_r, p, "rear")
        beta_dot = (Fyf + Fyr) / (m * v) - psi_dot
        psidd    = (lf * Fyf - lr * Fyr) / p["Iz"]
        return np.array([beta_dot, psidd])

    k1 = f(state)
    k2 = f(state + 0.5 * dt * k1)
    k3 = f(state + 0.5 * dt * k2)
    k4 = f(state + dt * k3)
    return state + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)


def linear_tyre(alpha: float, Fz: float, p: dict, which: str) -> float:
    """F_y = -C_alpha * alpha. Independent of Fz."""
    Cf = p["C_alpha_f"] if which == "front" else p["C_alpha_r"]
    return -Cf * alpha


# ---------------------------------------------------------------------------
# Segment-level driver: integrate any model's predict across a sim_df
# ---------------------------------------------------------------------------

def integrate_dst(
    sim_df: pd.DataFrame,
    platform: str,
    p: dict,
    step_fn: Callable[..., np.ndarray] = step_rk4_linear,
    **step_kwargs,
) -> pd.DataFrame:
    """Integrate a dynamic single-track over one segment.

    Returns a DataFrame with `yaw_rate_pred_rads` aligned to `sim_df.index`.
    Falls back to V0 passthrough on the passthrough platforms and below the
    speed floor (per-sample).
    """
    out = sim_df[["yaw_rate_pred_rads"]].copy()
    if platform in PASSTHROUGH_PLATFORMS:
        return out

    t     = sim_df["t_s"].to_numpy()
    delta = sim_df["delta_road_rad"].to_numpy()
    v     = sim_df["v_mps"].to_numpy()
    a_long = sim_df.get("a_long_mps2", pd.Series(np.zeros(len(t)))).to_numpy()
    yaw_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()

    n = len(t)
    psi_dot = np.zeros(n)
    state = np.array([0.0, yaw_v0[0] if n > 0 else 0.0])
    psi_dot[0] = state[1]

    p_local = dict(p)

    for i in range(1, n):
        dt = max(t[i] - t[i - 1], 1e-3)
        if v[i] < V_FLOOR_MPS:
            state = np.array([0.0, yaw_v0[i]])
            psi_dot[i] = yaw_v0[i]
            continue
        p_local["a_long_mps2"] = float(a_long[i])
        state = step_fn(state, float(delta[i]), float(v[i]), p_local, dt, **step_kwargs)
        # Stability guard — if state goes NaN/Inf, restart from V0.
        if not np.all(np.isfinite(state)):
            state = np.array([0.0, yaw_v0[i]])
        psi_dot[i] = state[1]

    out["yaw_rate_pred_rads"] = psi_dot
    return out


# ---------------------------------------------------------------------------
# Route-grouped fitter
# ---------------------------------------------------------------------------

@dataclass
class FitSpec:
    """Per-platform parameter spec passed to fit_with_route_cv.

    init   — initial guesses (list[float], one per fitted param)
    bounds — list of (lo, hi) tuples, same length as init
    names  — list[str], the parameter name written back to coeffs.json
    """
    init: list[float]
    bounds: list[tuple[float, float]]
    names: list[str]


def _segments_by_route(segment_paths: list[Path]) -> dict[str, list[Path]]:
    """Group segment paths by route (the 2nd-from-last path part).

    PATH SHAPE: <PLATFORM>/<DEVICE>/<ROUTE>/<IDX>/sim.csv
    """
    out: dict[str, list[Path]] = {}
    for p in segment_paths:
        if len(p.parents) < 2:
            continue
        route = p.parents[1].name
        out.setdefault(route, []).append(p)
    return out


def fit_with_route_cv(
    predict_factory: Callable[[dict], Callable],
    spec: FitSpec,
    *,
    platform: str,
    base_params: dict,
    segment_paths: list[Path],
    score_module,
    k_folds: int = 5,
    optimiser_method: str = "Nelder-Mead",
    max_iter: int = 200,
) -> dict:
    """Fit `spec.names` for one platform under k-fold route-grouped CV.

    Parameters
    ----------
    predict_factory : a callable that takes a params dict and returns a
        `predict(sim_df, platform)` function with current parameters baked in.
    spec : init / bounds / names for the parameters being optimised.
    platform : the platform to fit (one at a time — the caller iterates).
    base_params : the non-fitted parameters merged into every trial.
    segment_paths : full pool of segments for this platform.
    score_module : the loaded skills/score-model/score module
        (passed in so the fitter has no import-time skills dependency).
    k_folds : k for route-grouped CV (default 5).

    Returns
    -------
    dict with `params` (fitted), `route_cv_sigma_yaw`, `route_cv_sigma_cte`,
    `fold_pooled_yaw_rmse` (list), `converged`, `stuck_on_bound`.
    """
    from scipy.optimize import minimize  # local import

    if not segment_paths:
        return {"params": {n: v for n, v in zip(spec.names, spec.init)},
                "route_cv_sigma_yaw": None, "route_cv_sigma_cte": None,
                "fold_pooled_yaw_rmse": [], "converged": False,
                "stuck_on_bound": False, "n_segments": 0}

    routes = _segments_by_route(segment_paths)
    route_names = sorted(routes.keys())
    # Assign routes round-robin to k folds (deterministic).
    folds: list[list[Path]] = [[] for _ in range(k_folds)]
    for i, rn in enumerate(route_names):
        folds[i % k_folds].extend(routes[rn])

    def pooled_loss(x: np.ndarray, paths: list[Path]) -> float:
        params = dict(base_params)
        for name, val in zip(spec.names, x):
            params[name] = float(val)
        predict_fn = predict_factory(params)
        result = score_module.score(predict_fn, segment_paths=paths,
                                    platform_filter=platform)
        # Score returns yaw_rate_rmse (rad/s). NaN if every segment failed.
        rmse = result.get("yaw_rate_rmse")
        if rmse is None or not np.isfinite(rmse):
            return 1e6
        return float(rmse)

    # Stage 1 — fit on the full pool.
    x0 = np.array(spec.init, dtype=float)
    bounds_arr = np.array(spec.bounds, dtype=float)

    res = minimize(
        pooled_loss, x0, args=(segment_paths,),
        method=optimiser_method,
        options={"maxiter": max_iter, "xatol": 1e-3, "fatol": 1e-6},
    )
    x_fit = np.clip(res.x, bounds_arr[:, 0], bounds_arr[:, 1])
    fitted = {name: float(val) for name, val in zip(spec.names, x_fit)}
    stuck = _flag_stuck_on_bound(x_fit, bounds_arr)

    # Stage 2 — route-grouped CV σ using the fitted params (cheap; just score
    # each held-out fold once).
    fold_yaw: list[float] = []
    fold_cte: list[float] = []
    final_params = dict(base_params)
    final_params.update(fitted)
    final_predict = predict_factory(final_params)
    for i in range(k_folds):
        held_out = folds[i]
        if not held_out:
            continue
        result = score_module.score(final_predict, segment_paths=held_out,
                                    platform_filter=platform)
        yaw = result.get("yaw_rate_rmse")
        cte = result.get("cte_rmse")
        if yaw is not None and np.isfinite(yaw):
            fold_yaw.append(float(yaw))
        if cte is not None and np.isfinite(cte):
            fold_cte.append(float(cte))

    sigma_yaw = float(np.std(fold_yaw, ddof=1)) if len(fold_yaw) > 1 else None
    sigma_cte = float(np.std(fold_cte, ddof=1)) if len(fold_cte) > 1 else None

    return {
        "params": fitted,
        "route_cv_sigma_yaw": sigma_yaw,
        "route_cv_sigma_cte": sigma_cte,
        "fold_pooled_yaw_rmse": fold_yaw,
        "fold_pooled_cte_rmse": fold_cte,
        "converged": bool(res.success),
        "stuck_on_bound": stuck,
        "n_segments": len(segment_paths),
        "n_routes": len(route_names),
        "n_folds": k_folds,
        "final_loss": float(res.fun),
    }


def _flag_stuck_on_bound(x: np.ndarray, bounds: np.ndarray, tol: float = 0.02) -> bool:
    """True if any fitted param hit (within tol) the bound it was clamped against."""
    for xi, (lo, hi) in zip(x, bounds):
        span = max(hi - lo, 1e-9)
        if (xi - lo) / span < tol or (hi - xi) / span < tol:
            return True
    return False


# ---------------------------------------------------------------------------
# Coefficients I/O
# ---------------------------------------------------------------------------

def load_coeffs(model_dir: Path) -> dict:
    """Load coeffs.json for a catalogue model. Falls back to coeffs.default.json."""
    primary = model_dir / "coeffs.json"
    fallback = model_dir / "coeffs.default.json"
    for p in (primary, fallback):
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    raise FileNotFoundError(
        f"Neither coeffs.json nor coeffs.default.json found in {model_dir}"
    )


def write_coeffs(model_dir: Path, coeffs: dict) -> None:
    (model_dir / "coeffs.json").write_text(
        json.dumps(coeffs, indent=2, sort_keys=True) + "\n"
    )


def get_platform_params(platform: str, coeffs: dict) -> dict:
    """Compose base PLATFORM_PRIORS[platform] with the fitted overrides in coeffs."""
    base = dict(PLATFORM_PRIORS.get(platform, {}))
    over = coeffs.get(platform, {})
    if not isinstance(over, dict):
        return base
    # Pull primitive numeric fields only; ignore metadata like route_cv_sigma.
    for k, v in over.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            base[k] = float(v)
    return base


# ---------------------------------------------------------------------------
# Segment iteration (used by fit + smoke)
# ---------------------------------------------------------------------------

def discover_dev_segments(template_root: Path, platform: str) -> list[Path]:
    """List all sim.csv paths under data/sim/segments/<platform>/. Dev split only."""
    root = template_root / "data" / "sim" / "segments" / platform
    if not root.exists():
        return []
    return sorted(root.rglob("sim.csv"))


def find_template_root(start: Path) -> Path:
    """Walk up to find AGENTS.md + skills/ (the template root)."""
    start = start.resolve()
    for ancestor in (start, *start.parents):
        if (ancestor / "AGENTS.md").exists() and (ancestor / "skills").is_dir():
            return ancestor
    raise RuntimeError(f"could not find template root from {start}")
