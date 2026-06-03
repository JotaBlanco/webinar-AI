"""final-model predict — V1 baseline (m3.v3 converged rung-0 leader).

Why ship V1 unchanged?
- On the frozen dev split (402 segments), V1 gives yaw_rate_rmse = 0.005430
  rad/s and cte_rmse = 52.22 m. All five prefilled physics models, tested
  out-of-the-box and (for M1/M4) after fitting, failed to strictly beat V1
  on yaw RMSE within budget. M4 (relaxation-length) fitted on yaw lands at
  0.005634 / 52.10 — slightly worse yaw, marginally better CTE, net loss
  on the equally-weighted KPI.
- M1 (linear dynamic single-track) at carParams priors gave 0.00919 / 116.89
  (unfit). The L-BFGS-B fit with bounds converged in 0–1 iterations at the
  initial point (numerical gradient ≈ 0 with the heavy ODE objective),
  i.e. the bounds-constrained optimiser failed. Nelder-Mead fit was still
  running at budget end — see EXPERIMENTS.md.
- Per the task hard rule, we logged a rung-1 attempt in MODELS.md (m1);
  the shipped predict can still be rung-0.

This file inlines V1 so the final-model bundle is self-contained — no
relative imports from `code/v1_baseline.py` which is in a read-only
shared symlink.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


PLATFORM_PARAMS = {
    "FORD_F_150_LIGHTNING_MK1": {
        "use_per_segment_delta0": False,
        "delta0": 0.00133,
        "g": 0.863,
        "L_eff": 3.26,
        "K_us": 0.00350,
        "tau": 0.060,
    },
    "FORD_MUSTANG_MACH_E_MK1": {
        "use_per_segment_delta0": True,
        "delta0_fallback": -0.0001,
        "g": 0.891,
        "L_eff": 2.22,
        "K_us": 0.00150,
        "tau": 0.069,
    },
    "HYUNDAI_IONIQ_5": {
        "use_per_segment_delta0": True,
        "delta0_fallback": 0.0,
        "g": 0.938,
        "L_eff": 2.887,
        "K_us": 0.00289,
        "tau": 0.062,
    },
}


def _per_segment_delta0(
    sim_df: pd.DataFrame,
    fallback: float = 0.0,
    yr_thresh: float = 0.03,
    v_thresh: float = 5.0,
    min_rows: int = 50,
) -> float:
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """V1 single-track kinematic + understeer + first-order lag + per-segment δ₀.

    Reads only operating-contract columns: t_s, delta_road_rad, v_mps,
    yaw_rate_pred_rads. Tesla and any unknown platform falls through to V0
    passthrough (yaw_rate_pred_rads unchanged).
    """
    if platform not in PLATFORM_PARAMS:
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )
    p = PLATFORM_PARAMS[platform]
    delta0 = (
        _per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
        if p["use_per_segment_delta0"]
        else p["delta0"]
    )
    delta = (sim_df["delta_road_rad"].to_numpy() - delta0) * p["g"]
    v = sim_df["v_mps"].to_numpy()
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (p["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
