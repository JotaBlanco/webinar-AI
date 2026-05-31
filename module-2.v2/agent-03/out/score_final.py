"""Score the final model end-to-end via score-model."""
import sys
from pathlib import Path
ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-03")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "final-model"))
import os
os.chdir(ROOT)
from score import score, format_summary  # noqa
from predict import predict  # noqa

result = score(predict)
print(format_summary(result))
print()
print("=== Per-platform ===")
for p, m in result["per_platform"].items():
    print(f"  {p}: yaw_rmse={m['yaw_rate_rmse']:.5f}, cte_rmse={m['cte_rmse']:.3f}, yaw_bias={m['yaw_residual_mean']:+.5f}, cte_drift={m['cte_signed_mean']:+.3f}")
