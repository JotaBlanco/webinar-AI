"""affine-v1 — per-platform affine post-correction on V1.

y_hat = a * yr_v1 + b, with (a, b) fit from sim training data.
NOT structurally different from V1 — this is a benchmark to see if a thin
post-calibration captures most of V1's residual.
"""
from __future__ import annotations
import json
import pathlib
import numpy as np
import pandas as pd
import sys

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parents[1] / "code"))
from v1_baseline import predict_v1  # noqa: E402

COEFFS = json.loads((_HERE / "coeffs.json").read_text())


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = predict_v1(sim_df, platform)
    if platform not in COEFFS:
        return out
    a = COEFFS[platform]["a"]
    b = COEFFS[platform]["b"]
    yr = a * out["yaw_rate_pred_rads"].to_numpy() + b
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
