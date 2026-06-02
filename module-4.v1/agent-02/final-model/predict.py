"""Final model — V1 baseline + per-platform additive bias correction.

Variant per platform (selected by composite-KPI tournament on a route-grouped
80/20 dev split, see /out/train_eval.py):

    FORD_F_150_LIGHTNING_MK1   -> V1 (no bias, no ridge — at noise floor)
    FORD_MUSTANG_MACH_E_MK1    -> V1 + per-platform additive bias
    HYUNDAI_IONIQ_5            -> V1 + per-platform additive bias
    TESLA_MODEL_3              -> V0 passthrough (no truth channel)

Only the 8 allow-listed input columns are read from `sim_df`:
    t_s, delta_wheel_deg, delta_road_rad, v_mps, a_long_mps2,
    accel_pedal_pct, brake_pressed, yaw_rate_pred_rads.

The optional ridge residual head was investigated and improved yaw RMSE
slightly on every platform but degraded distance-resampled CTE RMSE on
Lightning and IONIQ-5, so it was rejected for the shipped model. See
`/REPORT.md` and `/out/train_eval.py` for the head-to-head.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

# Embed coefficients so predict.py is self-contained.
COEFFS_PATH = Path(__file__).resolve().parent / "coeffs.json"
_COEFFS = json.loads(COEFFS_PATH.read_text())

# ---- inline V1 (vendored from code/v1_baseline.py) ---------------------------
PLATFORM_PARAMS_V1 = {
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


def _per_segment_delta0(sim_df: pd.DataFrame, fallback: float = 0.0,
                        yr_thresh: float = 0.03, v_thresh: float = 5.0,
                        min_rows: int = 50) -> float:
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def _predict_v1(sim_df: pd.DataFrame, platform: str) -> np.ndarray:
    p = PLATFORM_PARAMS_V1[platform]
    delta0 = (_per_segment_delta0(sim_df, fallback=p["delta0_fallback"])
              if p["use_per_segment_delta0"] else p["delta0"])
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
    return yr


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """V1 + per-platform bias.

    Inputs (only columns read): t_s, delta_road_rad, v_mps, yaw_rate_pred_rads
    Tesla / unknown platforms fall through to the V0 passthrough.
    Returns DataFrame with `yaw_rate_pred_rads` aligned on sim_df.index.
    """
    if platform not in PLATFORM_PARAMS_V1:
        return pd.DataFrame(
            {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
            index=sim_df.index,
        )
    yr = _predict_v1(sim_df, platform)
    bias = float(_COEFFS["biases"].get(platform, 0.0))
    yr = yr + bias
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
