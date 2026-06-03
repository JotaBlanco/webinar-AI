"""Final model — v1-baseline-leader (TREE.json node, rung 0) with M4
(rung-orthogonal, relaxation-length) shipped as the structural alternative
we attempted.

Why V1 and not M4: on the frozen dev split V1 still wins on pooled yaw RMSE
(0.005430 vs 0.005634 for fitted M4). M4 is marginally better on CTE
(52.105 vs 52.215) but the dynamics-ladder gain we hoped for is not present
in the rung-orthogonal candidate. We log M4 in MODELS.md (rung: orthogonal)
as the climb attempt the task gates on.

predict(sim_df, platform) -> DataFrame with `yaw_rate_pred_rads` aligned
with `sim_df.index`. Operating-contract compliant — reads only the 8
declared sim-only columns.
"""
from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

# Make code/ importable so we can reuse the canonical V1 baseline.
HERE = Path(__file__).resolve().parent
TPL = HERE.parent
sys.path.insert(0, str(TPL / "code"))

from v1_baseline import predict_v1  # noqa: E402


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    """Predict yaw rate for one segment.

    Delegates to V1 baseline. Tesla / unknown platforms fall through to V0
    passthrough inside `predict_v1`.
    """
    return predict_v1(sim_df, platform)
