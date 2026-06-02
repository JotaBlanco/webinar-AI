"""Model D — V1 with a per-platform affine bias correction (s*y_v1 + b).

Same shape as V1 but with the post-hoc bias and gain removed. Two scalars
per platform, fit by closed-form LS over all qualifying sim/segments rows.

Note: this is NOT structurally distinct from V1 — it is a coefficient refit
and will be flagged by preflight. Included to quantify how much CTE the
signed yaw bias on Mach-E and IONIQ-5 was contributing.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "code"))
from v1_baseline import predict_v1  # type: ignore

_COEFFS = None


def _coeffs():
    global _COEFFS
    if _COEFFS is None:
        _COEFFS = json.loads((HERE / "coeffs.json").read_text())
    return _COEFFS


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    base = predict_v1(sim_df, platform)
    if platform == "TESLA_MODEL_3" or platform not in _coeffs():
        return base
    c = _coeffs()[platform]
    s = float(c.get("s", 1.0))
    b = float(c.get("b", 0.0))
    yr = base["yaw_rate_pred_rads"].to_numpy() * s + b
    return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
