"""V1 + per-platform ridge residual learner head.

Loads residual coefficients from residual_coeffs.json in this directory.
Tesla falls through to V0 passthrough as per V1 contract.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd

# Resolve V1 baseline (vendored alongside this file)
_HERE = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(_HERE))
from v1_baseline import predict_v1  # type: ignore

_COEFFS_PATH = _HERE / "residual_coeffs.json"
_COEFFS = json.loads(_COEFFS_PATH.read_text()) if _COEFFS_PATH.exists() else {}

FEATURE_NAMES = [
    "bias", "v", "v2",
    "delta", "delta_v", "delta_sq", "abs_delta",
    "ddelta", "ddelta_v", "ddelta_sq",
    "a_long", "brake",
    "yr_v1", "yr_v1_v", "yr_v1_sq", "yr_v1_abs",
    "yr_v1_delta", "yr_v1_v_sq",
    "delta_v2", "yr_v1_v2",
]


def _build_features(sim_df: pd.DataFrame, yr_v1: np.ndarray) -> np.ndarray:
    t = sim_df["t_s"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    d = sim_df["delta_road_rad"].to_numpy()
    a = sim_df["a_long_mps2"].to_numpy()
    a = np.nan_to_num(a, nan=0.0)
    b = sim_df["brake_pressed"].fillna(0).to_numpy() if hasattr(sim_df["brake_pressed"], "fillna") else np.nan_to_num(sim_df["brake_pressed"].to_numpy(), nan=0.0)
    dt = np.diff(t, prepend=t[0])
    dt = np.where(dt <= 0, 1e-3, dt)
    ddelta = np.diff(d, prepend=d[0]) / dt
    n = len(v)
    F = np.zeros((n, len(FEATURE_NAMES)))
    F[:, 0] = 1.0
    F[:, 1] = v
    F[:, 2] = v * v
    F[:, 3] = d
    F[:, 4] = d * v
    F[:, 5] = d * d
    F[:, 6] = np.abs(d)
    F[:, 7] = ddelta
    F[:, 8] = ddelta * v
    F[:, 9] = ddelta * ddelta
    F[:, 10] = a
    F[:, 11] = b
    F[:, 12] = yr_v1
    F[:, 13] = yr_v1 * v
    F[:, 14] = yr_v1 * yr_v1
    F[:, 15] = np.abs(yr_v1)
    F[:, 16] = yr_v1 * d
    F[:, 17] = yr_v1 * v * v
    F[:, 18] = d * v * v
    F[:, 19] = yr_v1 * v * v
    F = np.nan_to_num(F, nan=0.0, posinf=0.0, neginf=0.0)
    return F


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    base = predict_v1(sim_df, platform)
    yr_v1 = base["yaw_rate_pred_rads"].to_numpy()
    if platform not in _COEFFS:
        return base
    c = _COEFFS[platform]
    mu = np.array(c["mu"])
    sigma = np.array(c["sigma"])
    w = np.array(c["w"])
    F = _build_features(sim_df, yr_v1)
    Fz = (F - mu) / sigma
    resid_pred = Fz @ w
    yr = yr_v1 + resid_pred
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
