"""V2 lateral predictor — V1 shape with per-segment delta0 enabled for all
3 fittable platforms and re-fit (g, L_eff, K_us, tau, delta0_fallback) per
platform (see out/fit_v2.py + out/v2_params.json).

Tesla has no truth — passthrough of V0 baseline.

Contract: reads only the 8 allowlist columns from sim_df.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEF_PATH = Path(__file__).resolve().parent / "v2_params.json"
with _COEF_PATH.open() as _f:
    PLATFORM_PARAMS = json.load(_f)

# Per-segment delta0 helps Mach-E and Hyundai; F-150 prefers a fixed delta0.
_USE_PER_SEGMENT = {
    "FORD_F_150_LIGHTNING_MK1": False,
    "FORD_MUSTANG_MACH_E_MK1": True,
    "HYUNDAI_IONIQ_5": True,
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
    if platform not in PLATFORM_PARAMS:
        # Honest passthrough (Tesla and any unknown)
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )

    p = PLATFORM_PARAMS[platform]
    if _USE_PER_SEGMENT.get(platform, False):
        delta0 = _per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
    else:
        delta0 = p["delta0_fallback"]
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
