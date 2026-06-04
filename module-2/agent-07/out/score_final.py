"""Score the final-model/predict.py against all segments."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-07")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "final-model"))

from score import score, format_summary
from predict import predict  # noqa


if __name__ == "__main__":
    seg_root = ROOT / "data" / "sim" / "segments"
    paths = sorted(p for p in seg_root.glob("*/**/sim.csv") if p.is_file())
    print(f"found {len(paths)} segments")
    res = score(predict, segment_paths=paths)
    print(format_summary(res))
