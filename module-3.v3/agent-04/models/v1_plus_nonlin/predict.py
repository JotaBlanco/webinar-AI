"""Model A: V1 + nonlinear-tyre linear correction.

V1 leaves a residual structure correlated with |delta|*delta — signature of
tyre understeer saturating. We add a small linear correction:

    yr_corr = b0 + b1*|delta|*delta + b2*v*delta + b3*v^2*delta

fitted per-platform on V1 residuals against truth.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Ensure v1_baseline importable
_HERE = Path(__file__).resolve().parent
_AGENT_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_AGENT_ROOT / "code"))
from v1_baseline import predict_v1  # noqa: E402

_COEFFS_PATH = _HERE / "coeffs.json"
_COEFFS = json.loads(_COEFFS_PATH.read_text()) if _COEFFS_PATH.exists() else {}


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    base = predict_v1(sim_df, platform)
    yr = base["yaw_rate_pred_rads"].to_numpy().copy()
    p = _COEFFS.get(platform)
    if p is None:
        return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
    c = p["coef"]
    v = sim_df["v_mps"].to_numpy()
    delta = sim_df["delta_road_rad"].to_numpy()
    yr_corr = c[0] + c[1] * np.abs(delta) * delta + c[2] * v * delta + c[3] * v * v * delta
    yr_final = yr + yr_corr
    return pd.DataFrame({"yaw_rate_pred_rads": yr_final}, index=sim_df.index)
