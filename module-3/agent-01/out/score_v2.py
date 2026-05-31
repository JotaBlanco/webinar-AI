import sys, os
from pathlib import Path
ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-01")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "out"))
os.chdir(ROOT)
from score import score, format_summary  # type: ignore
from v2_predict import predict  # type: ignore
res = score(predict)
print(format_summary(res))
print(f"\nYAW_RMSE_OVERALL={res['yaw_rate_rmse']:.6f}")
print(f"CTE_RMSE_OVERALL={res['cte_rmse']:.4f}")
