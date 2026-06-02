"""M1 — Linear dynamic single-track (bicycle) with slip angles.

Two-state ODE: state = [β (sideslip), ψ̇ (yaw rate)], input δ (road wheel angle),
parameter v (longitudinal speed, measured per row). Linear tires.

Equations (see references/dynamics-formulations.md § Rung 1):

    α_f = β + l_f ψ̇ / v − δ
    α_r = β − l_r ψ̇ / v
    F_yf = −C_αf α_f
    F_yr = −C_αr α_r
    β̇  = (F_yf + F_yr) / (m v) − ψ̇
    ψ̈  = (l_f F_yf − l_r F_yr) / I_z

Numerics: RK4 step. At v < V_MIN_DYNAMIC the model passes V0
(`yaw_rate_pred_rads`) through — the small-angle dynamic model has a
1/v singularity that's noise below ~1.5 m/s.

Parameters per platform (fitted): C_αf, C_αr, I_z. Held at carParams: m,
l_f, l_r. Tesla returns V0 passthrough (no truth).
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
    v0_passthrough,
)


def _state_dot(state: np.ndarray, delta: float, v: float, p: dict) -> np.ndarray:
    beta, psi_dot = state
    alpha_f, alpha_r = slip_angles_linear(
        beta, psi_dot, delta, v, p["l_f"], p["l_r"]
    )
    F_yf = fy_linear(alpha_f, p["C_alpha_f"])
    F_yr = fy_linear(alpha_r, p["C_alpha_r"])
    beta_dot = (F_yf + F_yr) / (p["m"] * max(v, V_MIN_DYNAMIC)) - psi_dot
    psi_dd   = (p["l_f"] * F_yf - p["l_r"] * F_yr) / p["I_z"]
    return np.array([beta_dot, psi_dd])


def _run_dynamic(sim_df: pd.DataFrame, p: dict) -> np.ndarray:
    """Integrate the LDST ODE over a segment, falling back to V0 at low v."""
    t = sim_df["t_s"].to_numpy()
    delta = sim_df["delta_road_rad"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
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
            state = rk4_step(_state_dot, state, dt[i], delta[i], v[i], p)
        out[i] = state[1]
    return out


def predict_factory(platform: str, coeffs: dict[str, float]):
    """Build a predict callable for `fit-model` / `score-model`.

    `coeffs` overrides keys in the platform prior — typically C_αf, C_αr, I_z.
    """
    if platform == "TESLA_MODEL_3":
        def _passthrough(sim_df: pd.DataFrame) -> np.ndarray:
            return v0_passthrough(sim_df["yaw_rate_pred_rads"].to_numpy())
        return _passthrough

    p = prior(platform)
    p.update(coeffs)

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
