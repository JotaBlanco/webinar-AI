"""Final model — per-platform understeer + bias calibration of V0.

Model (per platform):
    yaw_pred = alpha * v0 / (1 + K * v^2) + beta

where v0 is the V0 KS baseline already provided as `yaw_rate_pred_rads`
in the input frame.

Coefficients live in `coeffs.json` next to this file. Tesla is identity.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEFFS_PATH = Path(__file__).resolve().parent / "coeffs.json"
_COEFFS = json.loads(_COEFFS_PATH.read_text())

_DEFAULT = {"alpha": 1.0, "K": 0.0, "beta": 0.0}


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Return a DataFrame aligned with sim_df.index containing yaw_rate_pred_rads."""
    coef = _COEFFS.get(platform, _DEFAULT)
    alpha = float(coef.get("alpha", 1.0))
    K     = float(coef.get("K", 0.0))
    beta  = float(coef.get("beta", 0.0))

    v  = sim_df["v_mps"].to_numpy(dtype=float)
    v0 = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)

    denom = 1.0 + K * v * v
    pred = alpha * v0 / denom + beta

    return pd.DataFrame({"yaw_rate_pred_rads": pred}, index=sim_df.index)
