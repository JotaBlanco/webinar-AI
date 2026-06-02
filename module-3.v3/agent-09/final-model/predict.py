"""Shipped model — V1 + per-platform affine bias correction.

Layered on top of `code/v1_baseline.predict_v1`. Per non-Tesla, non-Lightning
platform, applies y = s * y_v1 + b. Lightning passes through to V1 (route-
grouped holdout showed affine correction hurts Lightning CTE). Tesla passes
through (no truth, V0 only).

Coefficients in `coeffs.json`, fit by closed-form OLS on the full sim/segments
truth pool.
"""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
import pandas as pd

import sys
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "code"))
from v1_baseline import predict_v1  # type: ignore

_COEFFS = None


def _coeffs():
    global _COEFFS
    if _COEFFS is None:
        _COEFFS = json.loads((HERE / "coeffs.json").read_text())
    return _COEFFS


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw_rate_pred_rads for the supplied sim_df + platform.

    Args:
        sim_df: agent-facing 8-column input DataFrame.
        platform: platform string (e.g. 'FORD_MUSTANG_MACH_E_MK1').

    Returns:
        DataFrame with `yaw_rate_pred_rads`, indexed like sim_df.
    """
    base = predict_v1(sim_df, platform)
    cf = _coeffs()
    if platform == "TESLA_MODEL_3" or platform not in cf:
        return base
    c = cf[platform]
    s = float(c.get("s", 1.0))
    b = float(c.get("b", 0.0))
    if s == 1.0 and b == 0.0:
        return base
    yr = base["yaw_rate_pred_rads"].to_numpy() * s + b
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
