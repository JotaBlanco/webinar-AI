"""Quick V0 baseline score — pass-through of yaw_rate_pred_rads."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-05")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "_shared"))

import pandas as pd
from score import score, format_summary


def predict_v0(sim_df, platform):
    return pd.DataFrame(
        {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
        index=sim_df.index,
    )


# Use sim-only (mirror of grading) for honest comparison
seg_root = ROOT / "data" / "sim-only" / "segments"
paths = sorted(p for p in seg_root.glob("*/**/sim.csv") if p.is_file())
# but sim-only doesn't have truth. We need to score against data/sim (has truth).
seg_root = ROOT / "data" / "sim" / "segments"
paths = sorted(p for p in seg_root.glob("*/**/sim.csv") if p.is_file())
print(f"Found {len(paths)} segments")

res = score(predict_v0, segment_paths=paths)
print(format_summary(res))
