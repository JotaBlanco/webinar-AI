"""Score the final-model/predict against all sim/segments."""
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "final-model"))

spec = importlib.util.spec_from_file_location("predict", ROOT / "final-model" / "predict.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
predict = mod.predict

from score import score, format_summary  # noqa: E402

os.chdir(ROOT)
res = score(predict)
print(format_summary(res))
