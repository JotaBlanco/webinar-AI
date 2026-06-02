"""Affine post-correction on V1 yaw: yr = a*yr_v1 + b per platform.

Structurally different from V1: treats V1's output as a feature and applies
a linear correction. Attacks Mach-E and IONIQ-5 signed CTE drift via the
bias term; attacks Lightning over-shoot via the gain.
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
    "FORD_F_150_LIGHTNING_MK1": {"a": 0.98695, "b": -0.000444},
    "FORD_MUSTANG_MACH_E_MK1":   {"a": 0.97463, "b":  0.001696},
    "HYUNDAI_IONIQ_5":           {"a": 0.99207, "b":  0.000638},
}


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    v1_out = v1_baseline.predict_v1(sim_df, platform)
    yr_v1 = v1_out["yaw_rate_pred_rads"].to_numpy()
    if platform in COEFFS:
        c = COEFFS[platform]
        yr = c["a"] * yr_v1 + c["b"]
    else:
        yr = yr_v1
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
