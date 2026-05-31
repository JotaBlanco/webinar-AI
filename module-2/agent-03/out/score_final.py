"""Score the final-model predict() against all available sim segments."""
from __future__ import annotations
import sys
from pathlib import Path

REPO = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-03")
sys.path.insert(0, str(REPO / "skills" / "score-model"))
sys.path.insert(0, str(REPO / "final-model"))

from score import score, format_summary  # noqa: E402
from predict import predict  # noqa: E402


def gather_paths():
    root = REPO / "data" / "sim" / "segments"
    paths = sorted(root.glob("*/**/sim.csv"))
    keep = []
    for p in paths:
        with p.open() as f:
            header = f.readline().rstrip("\n").split(",")
        if "yaw_rate_meas_rads" in header and "yaw_rate_pred_rads" in header:
            keep.append(p)
    return keep


if __name__ == "__main__":
    paths = gather_paths()
    print(f"Scoring final model on {len(paths)} segments with truth.")
    result = score(predict, segment_paths=paths)
    print(format_summary(result))
