"""Score V3 vs V2 and V1."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-02")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "out"))

from score import score, format_summary  # noqa: E402
from predict_v3 import predict as predict_v3  # noqa: E402

res = score(predict_v3, segment_paths=None, final=False)
print(format_summary(res, top_n=5))
print()
print(f"V3: yaw={res['yaw_rate_rmse']:.6f} rad/s, cte={res['cte_rmse']:.4f} m")
# Per-platform
for plat, m in res["per_platform"].items():
    print(f"  {plat}: yaw={m['yaw_rate_rmse']:.5f}, cte={m['cte_rmse']:.3f}")
