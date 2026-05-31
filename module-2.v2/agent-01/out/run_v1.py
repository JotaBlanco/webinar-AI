"""Score the V1 (final-model) predictor."""
import glob
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "final-model"))
from score import score, format_summary  # noqa
from predict import predict  # noqa


if __name__ == "__main__":
    paths = sorted(glob.glob(str(ROOT / "data" / "sim" / "segments" / "*" / "**" / "sim.csv"), recursive=True))
    print(f"Found {len(paths)} segments")
    result = score(predict, segment_paths=paths)
    print(format_summary(result))
