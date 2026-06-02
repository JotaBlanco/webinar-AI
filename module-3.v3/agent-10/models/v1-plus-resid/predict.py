"""V1 + linear residual learner per platform.

Adds a small per-sample correction to V1's yaw rate prediction:
   yr_corrected = yr_v1 + intercept + sum(w_i * feature_i)

Features use only allowlist columns:
   v_mps, delta_road_rad, d_delta_dt (computed from t_s),
   a_long_mps2, yr_v1, |delta_road_rad|, sign(yr_v1)*yr_v1^2

Tesla falls through to V0 (no truth, no fit).
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
# Locate V1 baseline: agent-root/code/v1_baseline.py
sys.path.insert(0, str(HERE.parents[1] / "code"))
from v1_baseline import predict_v1  # noqa: E402


_COEFFS_PATH = HERE / "coeffs.json"
with _COEFFS_PATH.open() as fh:
    COEFFS = json.load(fh)


FEATURES = [
    "v_mps",
    "delta_road_rad",
    "d_delta_dt",
    "a_long_mps2",
    "yr_v1",
    "abs_delta",
    "yr_v1_sq_signed",
]


def _features(sim_df: pd.DataFrame, yr_v1: np.ndarray) -> np.ndarray:
    t = sim_df["t_s"].to_numpy()
    delta = sim_df["delta_road_rad"].to_numpy()
    d_delta_dt = np.gradient(delta, t) if len(t) > 1 else np.zeros_like(delta)
    return np.column_stack([
        sim_df["v_mps"].to_numpy(),
        delta,
        d_delta_dt,
        sim_df["a_long_mps2"].to_numpy(),
        yr_v1,
        np.abs(delta),
        np.sign(yr_v1) * (yr_v1 ** 2),
    ])


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    v1 = predict_v1(sim_df, platform)
    yr_v1 = v1["yaw_rate_pred_rads"].to_numpy()
    if platform not in COEFFS:
        return pd.DataFrame({"yaw_rate_pred_rads": yr_v1}, index=sim_df.index)
    cof = COEFFS[platform]
    X = _features(sim_df, yr_v1)
    w = np.array([cof["weights"][f] for f in FEATURES])
    correction = cof["intercept"] + X @ w
    return pd.DataFrame({"yaw_rate_pred_rads": yr_v1 + correction}, index=sim_df.index)
