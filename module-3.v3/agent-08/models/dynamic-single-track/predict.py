"""Dynamic single-track — placeholder predict that falls through to V1.

The model formulation lives in notes.md but was not implemented in this
agent's time budget. Falls through to V1 so the file is callable and the
registry entry is honest about its `status: drafting`.
"""
from __future__ import annotations
import sys
from pathlib import Path

import pandas as pd

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT / "code"))
from v1_baseline import predict_v1  # noqa: E402


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    return predict_v1(sim_df, platform)
