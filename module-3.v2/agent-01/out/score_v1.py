"""Score V1 final-model predict against all platforms (full set)."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-01")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "final-model"))

from score import score, format_summary  # noqa: E402
from predict import predict  # noqa: E402


if __name__ == "__main__":
    segs = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))
    print(f"Found {len(segs)} segments")
    res = score(predict, segment_paths=segs)
    print(format_summary(res))
