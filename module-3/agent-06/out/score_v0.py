"""Score V0 baseline (pass-through) using the score-model skill."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-06")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))

from score import score, format_summary  # noqa: E402


def predict_v0(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()}, index=sim_df.index)


if __name__ == "__main__":
    seg_root = ROOT / "data" / "sim" / "segments"
    paths = sorted(p for p in seg_root.glob("*/**/sim.csv") if p.is_file())
    print(f"n segments: {len(paths)}")
    result = score(predict_v0, segment_paths=paths)
    print(format_summary(result))
