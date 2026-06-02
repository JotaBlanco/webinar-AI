"""residual-learner — small linear residual correction on V1.

Idea: V1's yaw residual still correlates with measurable features. Fit a
per-platform linear regression on the V1 yaw residual using features that
are visible at grading time (allowlist):
    f = [yr_v1, |yr_v1|, v, v*yr_v1, ddelta_dt, delta, 1]
Predict the residual correction and ADD it back.

This is a structurally different *attack* on V1: V1 + learnt residual.
Not a re-fit of V1's parameters.
"""
from __future__ import annotations
import json, pathlib, sys
import numpy as np
import pandas as pd

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parents[1] / "code"))
from v1_baseline import predict_v1  # noqa: E402

COEFFS = json.loads((_HERE / "coeffs.json").read_text())


def _features(sim_df, yr_v1):
    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    d = sim_df["delta_road_rad"].to_numpy(dtype=float)
    if len(t) >= 2:
        dd = np.gradient(d, t)
    else:
        dd = np.zeros_like(d)
    one = np.ones_like(v)
    return np.column_stack([yr_v1, np.abs(yr_v1), v, v*yr_v1, dd, d, one])


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = predict_v1(sim_df, platform)
    if platform not in COEFFS:
        return out
    yr_v1 = out["yaw_rate_pred_rads"].to_numpy(dtype=float)
    F = _features(sim_df, yr_v1)
    w = np.asarray(COEFFS[platform]["w"], dtype=float)
    # F: (N, k), w: (k,). yaw_correction = F @ w. New prediction = V1 - residual_pred
    # We trained residual = V1 - truth, so to subtract residual:
    resid_pred = F @ w
    yr_new = yr_v1 - resid_pred
    return pd.DataFrame({"yaw_rate_pred_rads": yr_new}, index=sim_df.index)
