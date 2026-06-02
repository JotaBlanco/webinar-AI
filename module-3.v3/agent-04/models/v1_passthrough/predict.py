"""V1 passthrough — the baseline, registered as a candidate so we can compare
explicitly against structurally-different models."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_HERE = Path(__file__).resolve().parent
_AGENT_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_AGENT_ROOT / "code"))
from v1_baseline import predict_v1  # noqa: E402


def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    return predict_v1(sim_df, platform)
