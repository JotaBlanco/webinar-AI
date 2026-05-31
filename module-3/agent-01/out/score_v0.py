"""Score V0 passthrough."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-01")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "out"))

# score-model expects cwd to be agent root for default segment glob
import os
os.chdir(ROOT)

from score import score, format_summary  # type: ignore
from v0_predict import predict  # type: ignore

res = score(predict)
print(format_summary(res))
print()
print(f"YAW_RMSE_OVERALL={res['yaw_rate_rmse']:.6f}")
print(f"CTE_RMSE_OVERALL={res['cte_rmse']:.4f}")
