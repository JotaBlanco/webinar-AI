"""Score the V2 final-model."""
import sys, os
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-08")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "final-model"))

os.chdir(ROOT)

from score import score, format_summary
from predict import predict

result = score(predict)
print(format_summary(result))
