"""Quick V1 baseline scoring on dev (sim/segments)."""
import sys, os
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-01")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "code"))

from score import score, format_summary
from v1_baseline import predict_v1

r = score(predict_v1)
print(format_summary(r))
