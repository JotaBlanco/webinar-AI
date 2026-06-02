"""Model C: V1 + rich nonlinear + transient correction (8 features)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_AGENT_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_AGENT_ROOT / "code"))
from v1_baseline import predict_v1  # noqa: E402

_COEFFS_PATH = _HERE / "coeffs.json"
_COEFFS = json.loads(_COEFFS_PATH.read_text()) if _COEFFS_PATH.exists() else {}


def _features(sim_df: pd.DataFrame) -> np.ndarray:
    v = sim_df["v_mps"].to_numpy()
    delta = sim_df["delta_road_rad"].to_numpy()
    t = sim_df["t_s"].to_numpy()
    if len(t) >= 2:
        ddelta = np.gradient(delta, t)
    else:
        ddelta = np.zeros_like(delta)
    return np.column_stack([
        np.ones_like(v),
        np.abs(delta) * delta,
        v * delta,
        v * v * delta,
        delta ** 3,
        ddelta,
        ddelta * v,
        np.sign(delta) * delta * delta * v,
    ])


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    base = predict_v1(sim_df, platform)
    yr = base["yaw_rate_pred_rads"].to_numpy().copy()
    p = _COEFFS.get(platform)
    if p is None:
        return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
    coef = np.asarray(p["coef"], dtype=float)
    X = _features(sim_df)
    yr_final = yr + X @ coef
    return pd.DataFrame({"yaw_rate_pred_rads": yr_final}, index=sim_df.index)
