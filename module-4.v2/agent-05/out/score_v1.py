"""Quick scorer: score V1 baseline on dev set (all segments — no split for now)."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-05")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "code"))

from score import score, format_summary
from v1_baseline import predict_v1

res = score(predict_v1, segment_paths=None, platform_filter=None)
print(format_summary(res))
print()
print(f"OVERALL yaw={res['yaw_rate_rmse']:.6f}  cte={res['cte_rmse']:.4f}")
