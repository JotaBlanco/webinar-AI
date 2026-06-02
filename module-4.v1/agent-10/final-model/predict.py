"""Final model — V0 + per-platform ridge residual head.

Strategy
--------
V0 (kinematic single-track) emits `yaw_rate_pred_rads` in every sim.csv. We
add a per-platform additive correction `r(x; w)` that is a ridge-fit linear
combination of allowlist input features (steering angle, speed, accel,
steering rate and their interactions). Coefficients live in
`coefficients.json` next to this file. Tesla is V0 passthrough (no truth
channel — any deviation increases its RMSE).

Features (must mirror out/fit_corrections.py exactly):
    delta         = delta_road_rad
    delta_v       = delta_road_rad * v_mps
    delta_sq      = delta_road_rad * |delta_road_rad|
    v             = v_mps - 15.0
    a_long        = a_long_mps2
    delta_ddot    = d(delta_road_rad)/dt
    v_delta_ddot  = v_mps * d(delta_road_rad)/dt
    delta_abs_v   = |delta_road_rad| * v_mps

Trajectory: the grader integrates yaw_rate via cumulative dt + v_meas; the
score-model contract says x_m,y_m are optional. We omit them — the grader
integrates from yaw_rate_pred_rads, which is what the CTE definition uses.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEF_PATH = Path(__file__).resolve().parent / "coefficients.json"
with _COEF_PATH.open() as _f:
    _COEFS = json.load(_f)

_FEATURE_NAMES = _COEFS["feature_names"]
_V_CENTER = float(_COEFS["v_center"])


def _build_features(sim_df: pd.DataFrame) -> np.ndarray:
    delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    a_long = (
        sim_df["a_long_mps2"].to_numpy(dtype=float)
        if "a_long_mps2" in sim_df.columns
        else np.zeros_like(delta)
    )
    t = sim_df["t_s"].to_numpy(dtype=float)
    delta_dot = np.zeros_like(delta)
    if len(t) >= 2:
        dt = np.diff(t)
        dt = np.where(dt <= 0, 1e-3, dt)
        delta_dot[1:] = np.diff(delta) / dt
        delta_dot[0] = delta_dot[1]
    v_c = v - _V_CENTER
    feats = np.column_stack([
        delta,
        delta * v,
        delta * np.abs(delta),
        v_c,
        a_long,
        delta_dot,
        v * delta_dot,
        np.abs(delta) * v,
    ])
    return feats


def _apply_correction(platform: str, sim_df: pd.DataFrame, base_pred: np.ndarray) -> np.ndarray:
    plat = _COEFS["platforms"].get(platform)
    if plat is None or plat.get("ridge") is None:
        return base_pred
    ridge = plat["ridge"]
    feats = _build_features(sim_df)
    w0 = float(ridge["intercept"])
    ws = np.array([float(ridge["weights"][n]) for n in _FEATURE_NAMES], dtype=float)
    correction = w0 + feats @ ws
    return base_pred + correction


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return yaw_rate_pred_rads aligned with sim_df.index."""
    out = pd.DataFrame(index=sim_df.index)
    base = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
    if platform == "TESLA_MODEL_3":
        out["yaw_rate_pred_rads"] = base
        return out
    out["yaw_rate_pred_rads"] = _apply_correction(platform, sim_df, base)
    return out
