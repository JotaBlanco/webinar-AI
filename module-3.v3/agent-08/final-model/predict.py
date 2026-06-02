"""Final model — re-export of models/v1-plus-residual/predict.py.

V1 baseline + per-platform linear residual on allowlist features. See
`models/v1-plus-residual/notes.md` for formulation and
`models/v1-plus-residual/assessment.md` for scores.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT / "code"))
from v1_baseline import predict_v1  # noqa: E402

with open(_HERE / "coeffs.json") as fh:
    _COEFFS = json.load(fh)

FEATURE_NAMES = [
    "bias", "delta_road", "v", "v_delta", "ddelta", "v_ddelta",
    "v0_yaw", "abs_v0_yaw", "a_long", "v_sq_delta",
]


def _features(sim_df: pd.DataFrame) -> np.ndarray:
    t = sim_df["t_s"].to_numpy(dtype=float)
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    a_long = (
        sim_df["a_long_mps2"].to_numpy(dtype=float)
        if "a_long_mps2" in sim_df.columns else np.zeros_like(t)
    )
    v0_yaw = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
    if len(t) > 1:
        ddelta = np.gradient(delta, t)
    else:
        ddelta = np.zeros_like(delta)
    return np.column_stack([
        np.ones_like(t), delta, v, v * delta, ddelta, v * ddelta,
        v0_yaw, np.abs(v0_yaw), a_long, v * v * delta,
    ])


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    v1 = predict_v1(sim_df, platform)["yaw_rate_pred_rads"].to_numpy()
    if platform not in _COEFFS:
        return pd.DataFrame({"yaw_rate_pred_rads": v1}, index=sim_df.index)
    beta = np.asarray(_COEFFS[platform]["beta"], dtype=float)
    X = _features(sim_df)
    return pd.DataFrame(
        {"yaw_rate_pred_rads": v1 + X @ beta}, index=sim_df.index
    )
