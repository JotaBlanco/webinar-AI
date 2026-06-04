"""Benchmark V0 (passthrough) and V1 baseline against all dev segments."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "code"))

from score import score, format_summary  # noqa: E402
from v1_baseline import predict_v1  # noqa: E402


def v0_predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    return pd.DataFrame(
        {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
        index=sim_df.index,
    )


if __name__ == "__main__":
    import os
    os.chdir(str(ROOT))
    print("=== V0 (passthrough) ===")
    r0 = score(v0_predict)
    print(format_summary(r0))
    print()
    print("=== V1 baseline ===")
    r1 = score(predict_v1)
    print(format_summary(r1))
