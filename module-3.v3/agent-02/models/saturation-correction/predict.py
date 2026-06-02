"""Saturation correction: yr = a*yr_v1 + b + c * yr_v1 * (v*yr_v1)^2.

Attacks tyre nonlinearity that V1's linear understeer K_us misses.
The c-term scales yaw down/up at high lateral acceleration.
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

_HERE = Path(__file__).parent
_AGENT = _HERE.parent.parent
sys.path.insert(0, str(_AGENT / "code"))

import v1_baseline  # noqa: E402

COEFFS = {
    "FORD_F_150_LIGHTNING_MK1": {"a": 0.98419, "b": -0.000459, "c": 4.312e-04},
    "FORD_MUSTANG_MACH_E_MK1":   {"a": 0.97250, "b":  0.001696, "c": 3.527e-04},
    "HYUNDAI_IONIQ_5":           {"a": 0.99136, "b":  0.000638, "c": 1.201e-04},
}


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    v1_out = v1_baseline.predict_v1(sim_df, platform)
    yr_v1 = v1_out["yaw_rate_pred_rads"].to_numpy()
    if platform in COEFFS:
        c = COEFFS[platform]
        v = sim_df["v_mps"].to_numpy()
        a_lat = v * yr_v1
        yr = c["a"] * yr_v1 + c["b"] + c["c"] * yr_v1 * a_lat * a_lat
    else:
        yr = yr_v1
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
