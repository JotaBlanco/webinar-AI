"""Score V2 predict."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-05")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "final-model"))

from score import score, format_summary
from predict import predict

res = score(predict, segment_paths=None, platform_filter=None)
print(format_summary(res))
print()
print(f"V2 OVERALL  yaw={res['yaw_rate_rmse']:.6f}  cte={res['cte_rmse']:.4f}")
print(f"V1 ref      yaw=0.005874  cte=56.8071")
