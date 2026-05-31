"""Linear bicycle with understeer-gradient yaw-rate model, plus a first-order lag.

Model:
    yr_ss[k] = v[k] * (delta[k] - d0) / L_eff / (1 + K * v[k]^2)         (steady state)
    yr[0]    = yr_ss[0]
    yr[k+1]  = yr[k] + (dt / (tau + dt)) * (yr_ss[k+1] - yr[k])           (1st-order lag)

Per-platform parameters (L_eff, K, d0, tau) are fit by Nelder-Mead and
grid-search on 80% of segments held-out from a 20% dev split (seed=42). The
fit captures:
  - Effective wheelbase (L_eff) — corrects the kinematic prior.
  - Understeer gradient K (equivalent to 1/v_ch^2) — accounts for tyre
    side-slip in steady-state cornering.
  - Steering offset d0 — small rack/measurement bias.
  - Yaw-rate lag tau — accounts for the bandwidth of the actual yaw response
    versus the instantaneous steering input. Improves transients without
    hurting steady-state fit.

V0 baseline = pure kinematic single-track (KS) at nominal L, no understeer,
no lag.

Trajectory (x, y) is integrated by the grader using `_shared/traj_metrics.py`
from the predicted yaw rate and measured v; we only return yaw_rate_pred_rads.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


_COEFFS_PATH = Path(__file__).resolve().parent / "coeffs.json"
with _COEFFS_PATH.open("r") as _fh:
    COEFFS = json.load(_fh)


# Fallback for unseen platforms: nominal kinematic (KS) prediction.
NOM_L = {
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "TESLA_MODEL_3": 2.875,
}


def _apply_lag(yr_ss: np.ndarray, t: np.ndarray, tau: float) -> np.ndarray:
    """First-order low-pass on the steady-state yaw rate."""
    n = yr_ss.size
    if n == 0:
        return yr_ss
    if tau <= 1e-6:
        return yr_ss.copy()
    yr = np.empty(n, dtype=float)
    yr[0] = yr_ss[0]
    # Variable-dt 1st-order filter.
    dts = np.diff(t)
    for k in range(n - 1):
        dt = dts[k]
        if dt <= 0:
            yr[k + 1] = yr[k]
            continue
        alpha = dt / (tau + dt)
        yr[k + 1] = yr[k] + alpha * (yr_ss[k + 1] - yr[k])
    return yr


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw rate (rad/s) from measured (v_mps, delta_road_rad, t_s).

    Returns a DataFrame aligned with ``sim_df.index`` with column
    ``yaw_rate_pred_rads``.
    """
    v = sim_df["v_mps"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    t = sim_df["t_s"].to_numpy(dtype=float)

    if platform in COEFFS:
        c = COEFFS[platform]
        L_eff = c["L_eff"]
        K = c["K"]
        d0 = c["d0"]
        tau = c.get("tau", 0.0)
    else:
        L_eff = NOM_L.get(platform, 2.875)
        K = 0.0
        d0 = 0.0
        tau = 0.0

    yr_ss = v * (delta - d0) / L_eff / (1.0 + K * v * v)
    yr = _apply_lag(yr_ss, t, tau)

    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
