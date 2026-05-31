"""V2 predict: understeer + steering-rate lead + delta-cubic.

delta_eff = delta_road + tau * delta_dot + delta_bias + alpha3 * delta_road^3
yaw = scale * v * delta_eff / (L + K_us * v^2)
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

_COEFFS = None


def _load():
    global _COEFFS
    if _COEFFS is None:
        p = Path(__file__).parent / "coeffs_v2.json"
        _COEFFS = json.loads(p.read_text())
    return _COEFFS


_DEFAULT = {
    "K_us": 0.0028, "scale": 1.0, "delta_bias": 0.0,
    "tau": -0.06, "alpha3": 0.0, "L0": 3.0,
}


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    coeffs = _load().get(platform, _DEFAULT)
    K_us = coeffs["K_us"]
    scale = coeffs["scale"]
    delta_bias = coeffs["delta_bias"]
    tau = coeffs.get("tau", 0.0)
    alpha3 = coeffs.get("alpha3", 0.0)
    L = coeffs.get("L0", _DEFAULT["L0"])
    t = sim_df["t_s"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    d = sim_df["delta_road_rad"].to_numpy(dtype=float)
    if len(t) >= 3:
        ddot = np.gradient(d, t)
    else:
        ddot = np.zeros_like(d)
    d_eff = d + tau * ddot + delta_bias + alpha3 * (d ** 3)
    yaw = scale * v * d_eff / (L + K_us * v * v)
    return pd.DataFrame({"yaw_rate_pred_rads": yaw}, index=sim_df.index)
