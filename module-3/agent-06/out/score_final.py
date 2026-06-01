"""Score the final-model predict.py via score-model skill."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-06")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "final-model"))

os.chdir(ROOT)

from score import score, format_summary  # noqa: E402
from predict import predict  # noqa: E402


if __name__ == "__main__":
    seg_root = ROOT / "data" / "sim" / "segments"
    paths = sorted(p for p in seg_root.glob("*/**/sim.csv") if p.is_file())
    print(f"n segments: {len(paths)}")
    t0 = time.time()
    result = score(predict, segment_paths=paths)
    print(f"scored in {time.time()-t0:.1f}s")
    print(format_summary(result))
