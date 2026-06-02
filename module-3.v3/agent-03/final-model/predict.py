"""Shipped model: V1 baseline + per-platform gradient-boosted residual correction.

Structure-novel vs V1: V1 is closed-form (kinematic single-track + understeer +
first-order lag + δ₀). This model wraps V1 with a learned residual using
gradient-boosted decision trees over allowlist-safe input features.

predict(sim_df, platform) -> pd.DataFrame with column `yaw_rate_pred_rads`
aligned with sim_df.index.

Allowlist inputs used:
  t_s, delta_road_rad, v_mps, yaw_rate_pred_rads, a_long_mps2.
(Plus internally-computed yr_v1 from V1.)
"""
from __future__ import annotations

import importlib.util
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent

# Bundled V1 baseline (independent copy, no parent imports)
_v1_spec = importlib.util.spec_from_file_location("_v1_baseline", _HERE / "v1_baseline.py")
_v1 = importlib.util.module_from_spec(_v1_spec); _v1_spec.loader.exec_module(_v1)
predict_v1 = _v1.predict_v1


_MODELS = {}
for _pkl in _HERE.glob("*.pkl"):
    with _pkl.open("rb") as _f:
        _MODELS[_pkl.stem] = pickle.load(_f)


def _features(df: pd.DataFrame, yr_v1: np.ndarray) -> np.ndarray:
    t = df["t_s"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    v = df["v_mps"].to_numpy()
    yr_v0 = df["yaw_rate_pred_rads"].to_numpy()
    d_delta = np.gradient(delta, t) if len(t) > 1 else np.zeros_like(delta)
    a_lat_proxy = v * yr_v0
    a_long = df["a_long_mps2"].to_numpy()
    return np.column_stack([delta, d_delta, v, yr_v0, yr_v1, a_lat_proxy, a_long])


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    yr = predict_v1(sim_df, platform)["yaw_rate_pred_rads"].to_numpy().copy()
    if platform in _MODELS:
        feats = _features(sim_df, yr)
        m = np.all(np.isfinite(feats), axis=1)
        corr = np.zeros(len(yr))
        if m.any():
            corr[m] = _MODELS[platform]["model"].predict(feats[m])
        yr = yr + corr
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
