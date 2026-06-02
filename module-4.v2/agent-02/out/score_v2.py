"""Score V2 locally using the score-model skill against ALL sim segments
(dev pool; test split is refused unless final=True)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-02")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "final-model"))
sys.path.insert(0, str(ROOT / "code"))

from score import score, format_summary  # noqa: E402

# Import the V2 predict
from predict import predict as predict_v2  # noqa: E402
from v1_baseline import predict_v1  # noqa: E402

print("="*70)
print("V1 BASELINE")
print("="*70)
res_v1 = score(predict_v1, segment_paths=None, final=False)
print(format_summary(res_v1, top_n=5))

print()
print("="*70)
print("V2 (V1 + ridge residual head, per-platform)")
print("="*70)
res_v2 = score(predict_v2, segment_paths=None, final=False)
print(format_summary(res_v2, top_n=5))

print()
print("="*70)
print("DELTA")
print("="*70)
print(f"V1: yaw={res_v1['yaw_rate_rmse']:.6f} rad/s, cte={res_v1['cte_rmse']:.4f} m")
print(f"V2: yaw={res_v2['yaw_rate_rmse']:.6f} rad/s, cte={res_v2['cte_rmse']:.4f} m")
dy = (res_v2['yaw_rate_rmse'] - res_v1['yaw_rate_rmse']) / res_v1['yaw_rate_rmse'] * 100
dc = (res_v2['cte_rmse'] - res_v1['cte_rmse']) / res_v1['cte_rmse'] * 100
print(f"Yaw RMSE delta: {dy:+.2f}%")
print(f"CTE RMSE delta: {dc:+.2f}%")
