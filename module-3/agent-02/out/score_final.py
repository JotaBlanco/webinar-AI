"""Score the final model bundle."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "final-model"))
from score import score, format_summary  # noqa
from predict import predict  # noqa

res = score(predict)
print(format_summary(res, top_n=5))
