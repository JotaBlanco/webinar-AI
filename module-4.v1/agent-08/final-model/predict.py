"""Final model — V2c: V1 + per-platform scalar gain g and constant offset c.

Score (local, full sim-only set, all 3 fittable platforms; Tesla untouched):
  V0 passthrough : yaw 0.017632 rad/s,  CTE 218.16 m
  V1 baseline    : yaw 0.010612 rad/s,  CTE  75.65 m
  THIS (V2c)     : yaw 0.010527 rad/s,  CTE  72.59 m

Per-platform gain/offset fitted by OLS on yaw_rate_meas vs yr_v1, using an 80/20
segment-hash split (segments with seg_hash % 5 == 0 held out as dev). The fit is
yaw-RMSE-monotone on both train and held-out dev for every platform, so we accept
it. Trajectory CTE drops with it because per-platform yaw drift is what dominates
CTE growth.

Coefficients live in `gain_bias.json` next to this file.
Tesla has no truth channel — pass V1 through unchanged.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from v1_baseline import predict_v1  # noqa: E402

with open(_HERE / "gain_bias.json") as _f:
    GAIN_BIAS = json.load(_f)


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    yr_v1 = predict_v1(sim_df, platform)["yaw_rate_pred_rads"].to_numpy()
    gb = GAIN_BIAS.get(platform, {"gain": 1.0, "offset": 0.0})
    yr = gb["gain"] * yr_v1 + gb["offset"]
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
