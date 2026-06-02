"""Score the final-model/predict against the full sim corpus."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-10")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "final-model"))

from score import score, format_summary  # noqa: E402
from predict import predict  # noqa: E402


if __name__ == "__main__":
    r = score(predict)
    print(format_summary(r))
