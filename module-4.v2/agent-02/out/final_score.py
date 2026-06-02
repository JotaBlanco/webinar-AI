"""Final score: import predict from final-model/predict.py."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-02")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "final-model"))

from score import score, format_summary  # noqa: E402
from predict import predict  # noqa: E402

res = score(predict, segment_paths=None, final=False)
print(format_summary(res, top_n=8))
print()
print(f"FINAL V3: yaw={res['yaw_rate_rmse']:.6f} rad/s, cte={res['cte_rmse']:.4f} m")
for plat, m in res["per_platform"].items():
    print(f"  {plat}: yaw={m['yaw_rate_rmse']:.5f} bias={m['yaw_residual_mean']:+.5f} cte={m['cte_rmse']:.3f}")
