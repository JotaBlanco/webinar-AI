"""Baseline scoring: V0 = use yaw_rate_pred_rads as-is."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-09")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "_shared"))

from score import score, format_summary  # noqa: E402


def predict_v0(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].values}, index=sim_df.index)


def main() -> None:
    segs = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))
    print(f"Found {len(segs)} segments")
    res = score(predict_v0, segment_paths=segs)
    print(format_summary(res))


if __name__ == "__main__":
    main()
