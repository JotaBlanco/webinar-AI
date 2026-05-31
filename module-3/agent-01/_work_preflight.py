"""Run preflight + score the final-model on full data."""
import sys
from pathlib import Path

sys.path.insert(0, 'skills/pre-flight-final-model')
sys.path.insert(0, 'skills/score-model')
sys.path.insert(0, 'skills/make-train-dev-split')
from preflight import preflight
from score import score
from split import split

result = preflight('final-model')
print("PREFLIGHT:", result['passes'])
for c in result['checks']:
    print(f"  [{c['status']}] {c['name']}: {c['detail'][:120] if c['detail'] else ''}")
if not result['passes']:
    print("ERRORS:", result['errors'])

# Score final-model on full + on dev
sys.path.insert(0, str(Path('final-model').resolve()))
# Load predict via importlib
import importlib.util
spec = importlib.util.spec_from_file_location("final_predict", "final-model/predict.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
predict = mod.predict

import pandas as pd
def v0(sim_df, platform):
    out = pd.DataFrame(index=sim_df.index)
    out['yaw_rate_pred_rads'] = sim_df['yaw_rate_pred_rads']
    return out

tr, dv = split(dev_fraction=0.25, seed=42)

print("\n=== Final model on DEV ===")
r_dev = score(predict, segment_paths=dv)
print(f"yaw RMSE: {r_dev['yaw_rate_rmse']:.5f}, CTE RMSE: {r_dev['cte_rmse']:.3f}")
for k, vv in r_dev['per_platform'].items():
    print(f"  {k}: yaw={vv['yaw_rate_rmse']:.5f} CTE={vv['cte_rmse']:.3f} n_seg={vv['n_segments']}")
print(f"per_regime: {r_dev['per_regime']}")

print("\n=== V0 on DEV (same) ===")
r0_dev = score(v0, segment_paths=dv)
print(f"yaw RMSE: {r0_dev['yaw_rate_rmse']:.5f}, CTE RMSE: {r0_dev['cte_rmse']:.3f}")
for k, vv in r0_dev['per_platform'].items():
    print(f"  {k}: yaw={vv['yaw_rate_rmse']:.5f} CTE={vv['cte_rmse']:.3f}")

print("\n=== Final model on ALL FORD segments ===")
r_all = score(predict)
print(f"yaw RMSE: {r_all['yaw_rate_rmse']:.5f}, CTE RMSE: {r_all['cte_rmse']:.3f}")
for k, vv in r_all['per_platform'].items():
    print(f"  {k}: yaw={vv['yaw_rate_rmse']:.5f} CTE={vv['cte_rmse']:.3f} n_seg={vv['n_segments']}")
print(f"per_regime: {r_all['per_regime']}")
print(f"failed: {r_all['failed_segments']}")

print("\n=== V0 on ALL FORD segments ===")
r0_all = score(v0)
print(f"yaw RMSE: {r0_all['yaw_rate_rmse']:.5f}, CTE RMSE: {r0_all['cte_rmse']:.3f}")
for k, vv in r0_all['per_platform'].items():
    print(f"  {k}: yaw={vv['yaw_rate_rmse']:.5f} CTE={vv['cte_rmse']:.3f}")
