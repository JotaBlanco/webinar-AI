"""Final shipped model — thin re-export of models/v1_plus_rich.

This model is V1 + a per-platform 8-feature linear correction fitted on V1
residuals against truth. Features are derived only from the operating-contract
allowlist (delta, v, t, ddelta/dt). No truth channels are read at predict time.

KPIs (local on data/sim/segments/, full schema scored with allowlist-stripped
inputs to predict):
  V1 baseline:        yaw 0.005874   cte 56.81
  This model:         yaw 0.005552   cte 54.56
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_AGENT_ROOT = _HERE.parent
sys.path.insert(0, str(_AGENT_ROOT / "code"))
from v1_baseline import predict_v1  # noqa: E402

_COEFFS_PATH = _HERE / "coeffs.json"
_COEFFS = json.loads(_COEFFS_PATH.read_text()) if _COEFFS_PATH.exists() else {}


def _features(sim_df: pd.DataFrame) -> np.ndarray:
    v = sim_df["v_mps"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    t = sim_df["t_s"].to_numpy(dtype=float)
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
    """Return DataFrame with `yaw_rate_pred_rads` aligned with sim_df.index."""
    base = predict_v1(sim_df, platform)
    yr = base["yaw_rate_pred_rads"].to_numpy().copy()
    p = _COEFFS.get(platform)
    if p is None:
        # Tesla / unknown -> V1 (which falls back to V0)
        return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
    coef = np.asarray(p["coef"], dtype=float)
    X = _features(sim_df)
    yr_final = yr + X @ coef
    return pd.DataFrame({"yaw_rate_pred_rads": yr_final}, index=sim_df.index)
