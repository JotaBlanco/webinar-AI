"""Residual-learner predict.

predict_v1(sim_df, platform) -> yaw_rate baseline.
yaw_rate_pred = yaw_rate_v1 + w · phi(features).

Allowlist-safe features (none uses truth columns).
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]

# Lazy import V1
_spec = importlib.util.spec_from_file_location("v1_baseline", _ROOT / "code" / "v1_baseline.py")
_v1mod = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_v1mod)
predict_v1 = _v1mod.predict_v1

_COEFFS = json.loads((_HERE / "coeffs.json").read_text())


def _features(df: pd.DataFrame, yr_v1: np.ndarray) -> np.ndarray:
    t = df["t_s"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    v = df["v_mps"].to_numpy()
    yr_v0 = df["yaw_rate_pred_rads"].to_numpy()
    d_delta = np.gradient(delta, t) if len(t) > 1 else np.zeros_like(delta)
    d_yr_v1 = np.gradient(yr_v1, t) if len(t) > 1 else np.zeros_like(yr_v1)
    a_lat_proxy = v * yr_v0
    return np.column_stack([
        np.ones_like(delta), delta, d_delta, v, yr_v0, yr_v1,
        a_lat_proxy, delta * v, d_delta * v, d_yr_v1,
        np.sign(delta) * delta * delta,
    ])


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    v1_out = predict_v1(sim_df, platform)
    yr = v1_out["yaw_rate_pred_rads"].to_numpy().copy()
    if platform in _COEFFS:
        w = np.array(_COEFFS[platform]["weights"], dtype=float)
        feats = _features(sim_df, yr)
        m = np.all(np.isfinite(feats), axis=1)
        corr = np.zeros(len(yr))
        corr[m] = feats[m] @ w
        yr = yr + corr
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
