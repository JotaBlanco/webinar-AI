"""V2c: V1 + per-platform gain g and offset c (fitted on train, held-out on dev)."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
from v1_baseline import predict_v1

_GB_PATH = ROOT / "out" / "gain_bias.json"
with open(_GB_PATH) as f:
    GAIN_BIAS = json.load(f)


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    yr_v1 = predict_v1(sim_df, platform)["yaw_rate_pred_rads"].to_numpy(float)
    gb = GAIN_BIAS.get(platform, {"gain": 1.0, "offset": 0.0})
    yr = gb["gain"] * yr_v1 + gb["offset"]
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
