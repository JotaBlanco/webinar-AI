"""V1 + steering-rate feedforward.

Structural diff vs V1:
- V1 is purely a function of (delta_road, v) + a first-order lag on the state.
- This adds an input-derivative term: yr = yr_v1 + k_delta_dot * d(delta_road_eff)/dt.
- That term lets the model produce yaw-rate overshoot on rising steering edges,
  which is the second-order behaviour the first-order lag underfits.

Same allowlist as V1. Predicts yaw rate only; trajectory integration is left to
score-model (uses _shared.integrate_trajectory).
"""

from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd

# Import V1 baseline from agent's code/ directory.
_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "code"))
from v1_baseline import predict_v1, PLATFORM_PARAMS_V1  # noqa: E402


# Per-platform feed-forward gain. Fitted on dev — see fit script.
# These are starting points; will be refit.
FF_PARAMS = {
    "FORD_F_150_LIGHTNING_MK1": {"k_dd": 0.05, "gain_corr": 1.0028},
    "FORD_MUSTANG_MACH_E_MK1":  {"k_dd": 0.05, "gain_corr": 1.0099},
    "HYUNDAI_IONIQ_5":          {"k_dd": 0.05, "gain_corr": 1.0000},
}


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    base = predict_v1(sim_df, platform)
    if platform not in FF_PARAMS:
        return base
    p = FF_PARAMS[platform]
    yr = base["yaw_rate_pred_rads"].to_numpy(dtype=float).copy()
    t = sim_df["t_s"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    # Smoothed steering derivative
    if len(t) >= 3:
        ddelta = np.gradient(delta, t)
    else:
        ddelta = np.zeros_like(delta)
    # Feed-forward term scaled by speed (more dynamics at higher speed)
    yr_corrected = yr * p["gain_corr"] + p["k_dd"] * ddelta * np.clip(v, 0.0, 40.0) / 30.0
    return pd.DataFrame({"yaw_rate_pred_rads": yr_corrected}, index=sim_df.index)
