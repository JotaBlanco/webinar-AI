"""V1 + per-platform gradient-boosted residual correction."""
from __future__ import annotations

import importlib.util
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]

_spec = importlib.util.spec_from_file_location("v1_baseline", _ROOT / "code" / "v1_baseline.py")
_v1mod = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_v1mod)
predict_v1 = _v1mod.predict_v1

_MODELS = {}
for pkl in _HERE.glob("*.pkl"):
    plat = pkl.stem
    with pkl.open("rb") as f:
        _MODELS[plat] = pickle.load(f)


def _features(df, yr_v1):
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
