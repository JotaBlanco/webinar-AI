"""Score V1 against V0 on dev set + full set."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'skills' / 'score-model'))
sys.path.insert(0, str(ROOT / 'skills' / 'make-train-dev-split'))
sys.path.insert(0, str(ROOT / 'final-model'))

import pandas as pd
from score import score
from split import split
from predict import predict as predict_v1

def v0_predict(sim_df, platform):
    return pd.DataFrame({'yaw_rate_pred_rads': sim_df['yaw_rate_pred_rads'].values}, index=sim_df.index)

train, dev = split(dev_fraction=0.25, seed=42)
print(f"train={len(train)}  dev={len(dev)}")

print("\n=== DEV SET (held-out) ===")
res_v0 = score(v0_predict, segment_paths=dev)
res_v1 = score(predict_v1, segment_paths=dev)
print(f"V0:  yr_rmse={res_v0['yaw_rate_rmse']:.5f}  cte_rmse={res_v0['cte_rmse']:.4f}  n={res_v0['n_segments']}")
print(f"V1:  yr_rmse={res_v1['yaw_rate_rmse']:.5f}  cte_rmse={res_v1['cte_rmse']:.4f}  n={res_v1['n_segments']}")
print(f"     yr delta: {(res_v1['yaw_rate_rmse']-res_v0['yaw_rate_rmse'])/res_v0['yaw_rate_rmse']*100:+.1f}%")
print(f"     cte delta: {(res_v1['cte_rmse']-res_v0['cte_rmse'])/res_v0['cte_rmse']*100:+.1f}%")
for plat in res_v0['per_platform']:
    pv0 = res_v0['per_platform'][plat]
    pv1 = res_v1['per_platform'][plat]
    print(f"  {plat}: V0 yr={pv0['yaw_rate_rmse']:.5f}/cte={pv0['cte_rmse']:.4f}  V1 yr={pv1['yaw_rate_rmse']:.5f}/cte={pv1['cte_rmse']:.4f}")
print(f"V1 per_regime: ", {k:round(v['yaw_rate_rmse'],5) for k,v in res_v1['per_regime'].items()})

print("\n=== FULL SET (train+dev) ===")
res_v0_all = score(v0_predict)
res_v1_all = score(predict_v1)
print(f"V0:  yr_rmse={res_v0_all['yaw_rate_rmse']:.5f}  cte_rmse={res_v0_all['cte_rmse']:.4f}")
print(f"V1:  yr_rmse={res_v1_all['yaw_rate_rmse']:.5f}  cte_rmse={res_v1_all['cte_rmse']:.4f}")
print(f"     yr delta: {(res_v1_all['yaw_rate_rmse']-res_v0_all['yaw_rate_rmse'])/res_v0_all['yaw_rate_rmse']*100:+.1f}%")
print(f"     cte delta: {(res_v1_all['cte_rmse']-res_v0_all['cte_rmse'])/res_v0_all['cte_rmse']*100:+.1f}%")
for plat in res_v0_all['per_platform']:
    pv0 = res_v0_all['per_platform'][plat]
    pv1 = res_v1_all['per_platform'][plat]
    print(f"  {plat}: V0 yr={pv0['yaw_rate_rmse']:.5f}/cte={pv0['cte_rmse']:.4f}  V1 yr={pv1['yaw_rate_rmse']:.5f}/cte={pv1['cte_rmse']:.4f}")
