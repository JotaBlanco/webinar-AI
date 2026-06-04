"""Score V1 against all segments."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-04")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "out"))

from score import score, format_summary  # noqa: E402
from predict_v1 import predict  # noqa: E402

seg_root = ROOT / "data" / "sim" / "segments"
paths = sorted(p for p in seg_root.glob("*/**/sim.csv") if p.is_file())
result = score(predict, segment_paths=paths)
print(format_summary(result))
