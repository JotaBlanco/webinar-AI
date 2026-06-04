"""Score the final-model/predict against the full sim dataset (truth available)."""
import sys
from pathlib import Path
ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-01")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "final-model"))

from score import score, format_summary  # noqa: E402
from predict import predict as final_predict  # noqa: E402

seg_paths = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))
res = score(final_predict, segment_paths=seg_paths)
print(format_summary(res, top_n=3))
