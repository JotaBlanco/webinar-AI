"""Score V0 baseline (passthrough) on all platforms."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-02")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
from score import score, format_summary  # noqa: E402


def predict_v0(sim_df, platform):
    return pd.DataFrame(
        {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
        index=sim_df.index,
    )


if __name__ == "__main__":
    seg_paths = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))
    print(f"Found {len(seg_paths)} sim.csv files")
    result = score(predict_v0, segment_paths=seg_paths)
    print(format_summary(result, top_n=5))
