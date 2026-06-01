"""Score V0 baseline (just returns yaw_rate_pred_rads)."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-02")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "out"))

from score import score, format_summary  # noqa: E402
from v0_predict import predict  # noqa: E402

# Build segment paths under data/sim/segments
seg_root = ROOT / "data" / "sim" / "segments"
seg_paths = sorted(p for p in seg_root.glob("*/**/sim.csv") if p.is_file())
print(f"found {len(seg_paths)} segment files")

result = score(predict, segment_paths=seg_paths)
print(format_summary(result, top_n=5))
