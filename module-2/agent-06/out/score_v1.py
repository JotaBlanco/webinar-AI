import sys, os
from pathlib import Path
ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-06")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "out"))
os.chdir(ROOT)
from score import score, format_summary
from predict_v1 import predict
result = score(predict)
print(format_summary(result))
print()
print(f"yaw_rate_rmse: {result['yaw_rate_rmse']:.6f}")
print(f"cte_rmse:      {result['cte_rmse']:.6f}")
