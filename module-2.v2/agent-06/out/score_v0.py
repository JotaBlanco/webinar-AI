"""Score the V0 passthrough baseline."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-06")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))

import pandas as pd
from score import score, format_summary  # type: ignore


def predict_v0(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = pd.DataFrame(index=sim_df.index)
    out["yaw_rate_pred_rads"] = sim_df["yaw_rate_pred_rads"].astype(float)
    return out


if __name__ == "__main__":
    # Use sim segments (with truth) for scoring
    seg_root = ROOT / "data" / "sim" / "segments"
    seg_paths = sorted(p for p in seg_root.glob("*/**/sim.csv") if p.is_file())
    print(f"n_paths={len(seg_paths)}")
    res = score(predict_v0, segment_paths=seg_paths)
    print(format_summary(res))
