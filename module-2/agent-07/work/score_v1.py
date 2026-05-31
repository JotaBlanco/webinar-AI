"""Score predict_v1 with the official scorer."""
import sys, os
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-07")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "work"))
os.chdir(ROOT)

from score import score
from predict_v1 import predict as predict_v1

res = score(predict_v1)
print("V1 candidate (all FORD_*):")
print(f"  yaw_rate_rmse = {res['yaw_rate_rmse']:.6f}")
print(f"  cte_rmse      = {res['cte_rmse']:.4f}")
print(f"  n_segments    = {res['n_segments']}")
print("\nPer-platform:")
for k, v in res["per_platform"].items():
    print(f"  {k}: yr={v['yaw_rate_rmse']:.6f}, cte={v['cte_rmse']:.4f}")
print("\nPer-regime:")
for k, v in res["per_regime"].items():
    print(f"  {k}: yr={v['yaw_rate_rmse']:.6f}, n={v['n_samples']}")
