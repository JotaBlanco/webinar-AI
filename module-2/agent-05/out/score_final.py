"""Score the final-model/predict.py directly."""
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-05")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "final-model"))
os.chdir(ROOT)
from score import score, format_summary  # type: ignore

spec = importlib.util.spec_from_file_location("final_predict", ROOT / "final-model" / "predict.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

res = score(m.predict)
print(format_summary(res))
