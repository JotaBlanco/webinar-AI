"""V2b: V1 with per-platform gain+offset applied AND per-segment δ₀ also on F-150."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
from v1_baseline import _per_segment_delta0, predict_v1, PLATFORM_PARAMS_V1

# Load fitted gain/offset
_GB_PATH = ROOT / "out" / "gain_bias.json"
with open(_GB_PATH) as f:
    GAIN_BIAS = json.load(f)


def _v1_with_perseg_delta0_ford_f150(sim_df: pd.DataFrame) -> np.ndarray:
    p = PLATFORM_PARAMS_V1["FORD_F_150_LIGHTNING_MK1"]
    # Override: estimate per-seg δ₀ instead of constant
    delta0 = _per_segment_delta0(sim_df, fallback=p["delta0"])
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
    if platform == "FORD_F_150_LIGHTNING_MK1":
        yr_v1 = _v1_with_perseg_delta0_ford_f150(sim_df)
    else:
        yr_v1 = predict_v1(sim_df, platform)["yaw_rate_pred_rads"].to_numpy(float)
    gb = GAIN_BIAS.get(platform, {"gain": 1.0, "offset": 0.0})
    yr = gb["gain"] * yr_v1 + gb["offset"]
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
