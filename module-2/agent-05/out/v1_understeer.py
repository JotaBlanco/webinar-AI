"""V1: per-platform understeer-corrected yaw rate.

yaw = scale * v * (delta_road + delta_bias) / (L + K_us * v^2)
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEFFS = None


def _load():
    global _COEFFS
    if _COEFFS is None:
        p = Path(__file__).parent / "coeffs.json"
        _COEFFS = json.loads(p.read_text())
    return _COEFFS


_DEFAULT = {"K_us": 0.003, "scale": 1.0, "delta_bias": 0.0, "L0": 3.0}


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    coeffs = _load().get(platform, _DEFAULT)
    K_us = coeffs["K_us"]
    scale = coeffs["scale"]
    delta_bias = coeffs["delta_bias"]
    L = coeffs.get("L0", _DEFAULT["L0"])
    v = sim_df["v_mps"].to_numpy(dtype=float)
    d = sim_df["delta_road_rad"].to_numpy(dtype=float) + delta_bias
    yaw = scale * v * d / (L + K_us * v * v)
    return pd.DataFrame({"yaw_rate_pred_rads": yaw}, index=sim_df.index)
