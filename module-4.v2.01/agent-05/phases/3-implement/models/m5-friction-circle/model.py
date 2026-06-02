"""M5 — Long-lat coupled single-track with friction-circle envelope.

Two-state ODE: state = [β (sideslip), ψ̇ (yaw rate)], input δ (road wheel
angle) plus per-row a_long_mps2 and brake_pressed. Builds on M1's linear
tire — same demanded F_y per axle — but caps each axle's lateral force
to what's left after the longitudinal demand consumes the friction
envelope (the friction circle).

Equations (see references/dynamics-formulations.md § Rung 3 (variant) —
friction circle):

    F_x_total = m · a_long_mps2

    if brake_pressed:
        F_xf = brake_split_front · F_x_total
        F_xr = (1 − brake_split_front) · F_x_total
    else:
        F_xf = drive_split_front · F_x_total
        F_xr = (1 − drive_split_front) · F_x_total

    α_f = β + l_f ψ̇ / v − δ
    α_r = β − l_r ψ̇ / v
    F_yf_demand = -C_αf α_f
    F_yr_demand = -C_αr α_r

    F_yf = friction_circle_cap(F_yf_demand, F_xf, μ_f, F_zf_static)
    F_yr = friction_circle_cap(F_yr_demand, F_xr, μ_r, F_zr_static)

    β̇  = (F_yf + F_yr) / (m v) − ψ̇
    ψ̈  = (l_f F_yf − l_r F_yr) / I_z

Numerics: RK4 step. At v < V_MIN_DYNAMIC the model passes V0
(`yaw_rate_pred_rads`) through — the small-angle dynamic model has a
1/v singularity that's noise below ~4 m/s.

Parameters per platform (fitted): C_αf, C_αr, I_z, μ_f, μ_r,
drive_split_front, brake_split_front. Held at carParams: m, l_f, l_r,
g (used to derive static axle F_z). Tesla returns V0 passthrough (no
truth).
"""
from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

# Make _shared importable when invoked from anywhere
TPL = Path(__file__).resolve().parents[4]
if str(TPL) not in sys.path:
    sys.path.insert(0, str(TPL))

from _shared.physics_core import (  # noqa: E402
    V_MIN_DYNAMIC,
    prior,
    rk4_step,
    safe_dt,
    slip_angles_linear,
    fy_linear,
    friction_circle_cap,
    axle_load_static,
    v0_passthrough,
)


def _state_dot(
    state: np.ndarray,
    delta: float,
    v: float,
    a_long: float,
    brake: float,
    p: dict,
) -> np.ndarray:
    beta, psi_dot = state

    # M1-style linear demanded F_y per axle.
    alpha_f, alpha_r = slip_angles_linear(
        beta, psi_dot, delta, v, p["l_f"], p["l_r"]
    )
    F_yf_demand = fy_linear(alpha_f, p["C_alpha_f"])
    F_yr_demand = fy_linear(alpha_r, p["C_alpha_r"])

    # Distribute longitudinal force between axles. brake is 0/1.
    F_x_total = p["m"] * a_long
    if brake >= 0.5:
        split_f = p["brake_split_front"]
    else:
        split_f = p["drive_split_front"]
    F_xf = split_f * F_x_total
    F_xr = (1.0 - split_f) * F_x_total

    # Friction-circle cap per axle (axle-level F_z, sum of both wheels).
    F_yf = friction_circle_cap(F_yf_demand, F_xf, p["mu_f"], p["F_zf"])
    F_yr = friction_circle_cap(F_yr_demand, F_xr, p["mu_r"], p["F_zr"])

    beta_dot = (F_yf + F_yr) / (p["m"] * max(v, V_MIN_DYNAMIC)) - psi_dot
    psi_dd   = (p["l_f"] * F_yf - p["l_r"] * F_yr) / p["I_z"]
    return np.array([beta_dot, psi_dd])


def _run_dynamic(sim_df: pd.DataFrame, p: dict) -> np.ndarray:
    """Integrate the friction-circle ODE over a segment, falling back to V0 at low v."""
    t = sim_df["t_s"].to_numpy()
    delta = sim_df["delta_road_rad"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    a_long = sim_df["a_long_mps2"].to_numpy()
    # `brake_pressed` is in the operating-contract allowlist but not
    # always present in the per-platform sim.csv (e.g. Hyundai Ioniq 5).
    # Fall back to inferring brake-vs-drive from the sign of a_long.
    if "brake_pressed" in sim_df.columns:
        brake = sim_df["brake_pressed"].to_numpy().astype(float)
    else:
        brake = (a_long < 0.0).astype(float)
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    dt = safe_dt(t)

    n = len(t)
    out = np.empty(n, dtype=float)
    state = np.array([0.0, yr_v0[0]])  # start at V0 yaw rate

    for i in range(n):
        if v[i] < V_MIN_DYNAMIC:
            out[i] = yr_v0[i]
            # snap state to V0 to avoid stale carry-over across stop-go
            state = np.array([0.0, yr_v0[i]])
            continue
        # Step from i-1 to i with mid-step inputs (use current row inputs).
        if i > 0:
            state = rk4_step(
                _state_dot, state, dt[i],
                delta[i], v[i], a_long[i], brake[i], p,
            )
        out[i] = state[1]
    return out


def predict_factory(platform: str, coeffs: dict[str, float]):
    """Build a predict callable for `fit-model` / `score-model`.

    `coeffs` overrides keys in the platform prior — typically
    C_αf, C_αr, I_z, μ_f, μ_r, drive_split_front, brake_split_front.
    F_zf, F_zr are derived from (m, l_f, l_r, g) inside this factory —
    they are NOT fitted.
    """
    if platform == "TESLA_MODEL_3":
        def _passthrough(sim_df: pd.DataFrame) -> np.ndarray:
            return v0_passthrough(sim_df["yaw_rate_pred_rads"].to_numpy())
        return _passthrough

    p = prior(platform)
    # Default mu_f / mu_r from the platform's single mu prior.
    p["mu_f"] = p["mu"]
    p["mu_r"] = p["mu"]
    # AWD prior — all three trucks in this dataset are AWD.
    p["drive_split_front"] = 0.5
    # Standard brake bias front-heavy.
    p["brake_split_front"] = 0.6
    p.update(coeffs)

    # Static per-axle normal loads (total per axle, in N — not per wheel).
    F_zf, F_zr = axle_load_static(p["m"], p["l_f"], p["l_r"], p["g"])
    p["F_zf"] = F_zf
    p["F_zr"] = F_zr

    def _predict(sim_df: pd.DataFrame) -> np.ndarray:
        return _run_dynamic(sim_df, p)

    return _predict


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Operating-contract entry point used by the canonical grader."""
    import json

    coeffs_path = Path(__file__).parent / "coeffs.json"
    if coeffs_path.is_file():
        with coeffs_path.open() as f:
            all_coeffs = json.load(f)
        c = all_coeffs.get(platform, {})
    else:
        c = {}

    fn = predict_factory(platform, c)
    yr = fn(sim_df)
    out = sim_df[["yaw_rate_pred_rads"]].copy()
    out["yaw_rate_pred_rads"] = yr
    return out
