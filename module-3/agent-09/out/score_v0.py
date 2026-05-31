"""Score the V0 baseline (just echo back yaw_rate_pred_rads).

Establishes the starting yaw-rate RMSE and CTE RMSE per platform.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-09")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "_shared"))

from score import score, format_summary  # noqa: E402


def predict_v0(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = pd.DataFrame(index=sim_df.index)
    out["yaw_rate_pred_rads"] = sim_df["yaw_rate_pred_rads"].astype(float).to_numpy()
    return out


if __name__ == "__main__":
    # Use the sim/ segments (truth available) for scoring.
    seg_root = ROOT / "data" / "sim" / "segments"
    seg_paths = sorted(p for p in seg_root.glob("*/**/sim.csv") if p.is_file())
    print(f"scoring {len(seg_paths)} segments")
    result = score(predict_v0, segment_paths=seg_paths)
    print(format_summary(result, top_n=5))
