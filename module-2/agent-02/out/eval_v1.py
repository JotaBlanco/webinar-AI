"""Score V1 predict() on the full sim/segments set (where truth is available)."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "final-model"))
from out.scorer import score, v0_predict
import predict as v1mod

res_v0 = score(v0_predict)
print(f"V0 yaw_rate_rmse={res_v0['yaw_rate_rmse']:.6f}  cte_rmse={res_v0['cte_rmse']:.4f}  n_seg={res_v0['n_segments']}")
for plat, m in res_v0["per_platform"].items():
    print(f"   V0  {plat}: yaw={m['yaw_rate_rmse']:.5f}  cte={m['cte_rmse']:.3f}")

res_v1 = score(v1mod.predict)
print(f"\nV1 yaw_rate_rmse={res_v1['yaw_rate_rmse']:.6f}  cte_rmse={res_v1['cte_rmse']:.4f}  n_seg={res_v1['n_segments']}")
for plat, m in res_v1["per_platform"].items():
    print(f"   V1  {plat}: yaw={m['yaw_rate_rmse']:.5f}  cte={m['cte_rmse']:.3f}")

print(f"\nyaw improvement: {(res_v0['yaw_rate_rmse']-res_v1['yaw_rate_rmse'])/res_v0['yaw_rate_rmse']*100:.1f}%")
print(f"cte improvement: {(res_v0['cte_rmse']-res_v1['cte_rmse'])/res_v0['cte_rmse']*100:.1f}%")
