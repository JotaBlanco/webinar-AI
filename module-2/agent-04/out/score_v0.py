"""Score the V0 baseline across all platforms."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-04")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "out"))

from score import score, format_summary  # noqa: E402
from predict_v0 import predict  # noqa: E402


def main():
    seg_root = ROOT / "data" / "sim" / "segments"
    paths = sorted(p for p in seg_root.glob("*/**/sim.csv") if p.is_file())
    result = score(predict, segment_paths=paths)
    print(format_summary(result))


if __name__ == "__main__":
    main()
