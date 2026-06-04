import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-05")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "out"))

from score import score, format_summary
from predict_v1 import predict

seg_root = ROOT / "data" / "sim" / "segments"
paths = sorted(p for p in seg_root.glob("*/**/sim.csv") if p.is_file())
print(f"Found {len(paths)} segments")

res = score(predict, segment_paths=paths)
print(format_summary(res))
