"""V1 + per-platform constant yaw-rate offset chosen to cancel CTE drift.

CTE drift is approximately ⟨yaw_bias⟩ · ∫ v dt = ⟨yaw_bias⟩ · distance.
For Mach-E, V1 has yaw_bias = -0.00142 rad/s but cte_drift = -22 m, meaning
the *time-pooled* yaw bias understates the CTE-relevant integrated bias.

Approach: add a small constant correction `delta_yr` per platform; solve for
the value that drives pooled signed CTE to zero on training data. Structurally
this is V1 + a 1-parameter bias correction in the *trajectory-integration* loss
domain — different objective from V1's RMS-yaw fit. The signed cte_drift after
V1 is the gradient direction we need.

Implementation: pre-fitted from `out/fit_cte_debias.py`.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "code"))
from v1_baseline import predict_v1  # noqa: E402


with (HERE / "coeffs.json").open() as fh:
    COEFFS = json.load(fh)


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    v1 = predict_v1(sim_df, platform)
    yr = v1["yaw_rate_pred_rads"].to_numpy()
    if platform not in COEFFS:
        return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
    delta_yr = COEFFS[platform]["delta_yr"]
    return pd.DataFrame({"yaw_rate_pred_rads": yr + delta_yr}, index=sim_df.index)
