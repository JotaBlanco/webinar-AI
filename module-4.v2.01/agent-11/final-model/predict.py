"""V1 + per-platform lateral-acceleration load-transfer correction.

Variant of the m3.v3 V1 baseline. After V1's first-order-lagged steady-state
yaw is computed, we apply a per-platform multiplicative correction
parameterised in V1's predicted lateral acceleration proxy (a_lat ~= yr_v1 * v):

    yr_pred = yr_v1 * (1 + k1 * a_lat + k2 * a_lat^2)

For HYUNDAI_IONIQ_5 the correction collapses to identity (k1 = k2 = 0):
its train/dev residuals are not aligned with V1 a_lat, so any correction
overfits. For FORD_F_150_LIGHTNING_MK1 (and FORD_MUSTANG_MACH_E_MK1) the
correction targets the load-transfer/understeer-shift residual.

Tesla → V0 passthrough (no truth channel available).

Coefficients fitted on the frozen train split (route-grouped, 60% of segments).
Self-contained: reads only the 8-column sim-only contract.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


PLATFORM_PARAMS = {
    "FORD_F_150_LIGHTNING_MK1": {
        "use_per_segment_delta0": False, "delta0": 0.00133,
        "g": 0.863, "L_eff": 3.26, "K_us": 0.00350, "tau": 0.060,
        "k1": -0.00331, "k2": -0.00063,
    },
    "FORD_MUSTANG_MACH_E_MK1": {
        "use_per_segment_delta0": True, "delta0_fallback": -0.0001,
        "g": 0.891, "L_eff": 2.22, "K_us": 0.00150, "tau": 0.069,
        "k1":  0.00179, "k2": -0.00271,
    },
    "HYUNDAI_IONIQ_5": {
        "use_per_segment_delta0": True, "delta0_fallback": 0.0,
        "g": 0.938, "L_eff": 2.887, "K_us": 0.00289, "tau": 0.062,
        "k1": 0.0, "k2": 0.0,
    },
}


def _per_segment_delta0(sim_df: pd.DataFrame, fallback: float,
                         yr_thresh: float = 0.03, v_thresh: float = 5.0,
                         min_rows: int = 50) -> float:
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    if platform not in PLATFORM_PARAMS:
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )
    p = PLATFORM_PARAMS[platform]
    delta0 = (
        _per_segment_delta0(sim_df, p["delta0_fallback"])
        if p["use_per_segment_delta0"] else p["delta0"]
    )
    delta = (sim_df["delta_road_rad"].to_numpy() - delta0) * p["g"]
    v = sim_df["v_mps"].to_numpy()
    t = sim_df["t_s"].to_numpy()
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (p["tau"] + dt)
    yr_v1 = np.empty_like(yr_ss)
    yr_v1[0] = yr_ss[0]
    for i in range(1, len(yr_v1)):
        yr_v1[i] = yr_v1[i - 1] + alpha[i] * (yr_ss[i] - yr_v1[i - 1])
    a_lat = yr_v1 * v
    yr = yr_v1 * (1.0 + p["k1"] * a_lat + p["k2"] * a_lat * a_lat)
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
