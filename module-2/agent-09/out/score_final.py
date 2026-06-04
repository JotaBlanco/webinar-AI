"""Final scoring: load the actual final-model predict and score it through the skill."""
import sys, os, importlib.util
from pathlib import Path
ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-09")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "final-model"))
os.chdir(ROOT)
from score import score, format_summary

spec = importlib.util.spec_from_file_location("final_predict", str(ROOT / "final-model" / "predict.py"))
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)

result = score(mod.predict)
print(format_summary(result))
print("\nFINAL: yaw=%f, cte=%f" % (result["yaw_rate_rmse"], result["cte_rmse"]))
