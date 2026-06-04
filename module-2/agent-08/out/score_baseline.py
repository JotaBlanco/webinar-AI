"""Score the V0 baseline."""
import sys, os
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-08")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "out"))

os.chdir(ROOT)  # so score-model default glob works

from score import score, format_summary
from predict_v0 import predict

result = score(predict)
print(format_summary(result))
