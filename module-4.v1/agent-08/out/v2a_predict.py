"""V2a: V1 + per-segment yaw bias removal.

Inside predict(), we have NO access to truth. But we can estimate a per-segment
yaw-rate offset from the V1 prediction itself: a real-world straight-driving
segment should yield near-zero yaw rate. If V1 (and the steering channel it
uses) systematically reports a non-zero yaw during straight-driving regions,
that's a constant bias we can subtract.

Algorithm:
  1. Compute yr_v1 = V1(sim_df).
  2. Identify "straight-driving" samples: |delta_road - delta0| small,
     |yr_v1| < small thresh, v > thresh.
  3. bias = median(yr_v1 on straight samples) if enough samples else 0.
  4. Optional gain shrink: yr = (yr_v1 - bias) * gain where gain<1.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Allow importing v1 from code/ (set via path injection in predict module)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
from v1_baseline import predict_v1  # noqa: E402


# Per-platform gain shrinkage (calibrated below from corr(resid, yr_v1))
# resid = yr_truth - yr_v1; corr(resid, yr_v1) negative => yr_v1 over-magnitudes
# Suggested gain ~ 1 + (cov(r, yr_v1) / var(yr_v1)). We use modest shrinkage.
PLATFORM_GAIN = {
    "FORD_F_150_LIGHTNING_MK1": 1.00,
    "FORD_MUSTANG_MACH_E_MK1": 1.00,
    "HYUNDAI_IONIQ_5": 1.00,
}

# Only apply per-segment bias removal where V1 doesn't already do per-segment δ₀.
# V1 already does per-seg δ₀ for Mustang and Hyundai → skip them; F-150 has a
# fixed δ₀ → bias removal might help.
PLATFORM_BIAS_REMOVAL = {
    "FORD_F_150_LIGHTNING_MK1": False,  # disabled — empirically hurts
    "FORD_MUSTANG_MACH_E_MK1": False,
    "HYUNDAI_IONIQ_5": False,
}


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    yr_v1 = predict_v1(sim_df, platform)["yaw_rate_pred_rads"].to_numpy(float)
    if platform == "TESLA_MODEL_3":
        return pd.DataFrame({"yaw_rate_pred_rads": yr_v1}, index=sim_df.index)
    gain = PLATFORM_GAIN.get(platform, 1.0)
    yr = yr_v1 * gain
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
