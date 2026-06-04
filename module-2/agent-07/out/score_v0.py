"""Score V0 passthrough baseline."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-07")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "_shared"))

from score import score, format_summary


def predict_v0(sim_df, platform):
    out = sim_df[["yaw_rate_pred_rads"]].copy()
    return out


if __name__ == "__main__":
    # gather all segment paths
    seg_root = ROOT / "data" / "sim" / "segments"
    paths = sorted(p for p in seg_root.glob("*/**/sim.csv") if p.is_file())
    print(f"found {len(paths)} segments")
    res = score(predict_v0, segment_paths=paths)
    print(format_summary(res))
