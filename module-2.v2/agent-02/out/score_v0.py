"""Score V0 baseline (the yaw_rate_pred_rads already in sim.csv).

Usage: python3 score_v0.py
"""
from __future__ import annotations
import sys
from pathlib import Path

import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-02")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
from score import score, format_summary  # noqa: E402


def predict_v0(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = pd.DataFrame(index=sim_df.index)
    out["yaw_rate_pred_rads"] = sim_df["yaw_rate_pred_rads"].astype(float)
    return out


if __name__ == "__main__":
    segs = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))
    res = score(predict_v0, segment_paths=segs)
    print(format_summary(res))
