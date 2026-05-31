"""Score the V1 model (predict.py in final-model) on dev + on full FORD set."""
import sys, importlib.util
from pathlib import Path

sys.path.insert(0, 'skills/score-model')
sys.path.insert(0, 'skills/make-train-dev-split')
sys.path.insert(0, '_shared')

from score import score
from split import split

# Load final-model/predict.py
spec = importlib.util.spec_from_file_location('agent10_predict', 'final-model/predict.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
predict = mod.predict


def report(label, paths=None, platform_filter=None):
    r = score(predict, segment_paths=paths, platform_filter=platform_filter)
    print(f'=== {label} ===')
    print(f'  yaw RMSE = {r["yaw_rate_rmse"]:.6f}  CTE RMSE = {r["cte_rmse"]:.3f}  n_seg={r["n_segments"]} n_samp={r["n_samples"]} failed={r["failed_segments"]}')
    for k, v in r['per_platform'].items():
        print(f'    {k}: yaw={v["yaw_rate_rmse"]:.6f}  CTE={v["cte_rmse"]:.3f}  n_seg={v["n_segments"]}')
    for k, v in r['per_regime'].items():
        print(f'    [{k}]: yaw={v["yaw_rate_rmse"]:.6f}  n={v["n_samples"]}')


# V0 baseline for comparison
import pandas as pd
def v0(sim_df, platform):
    out = pd.DataFrame(index=sim_df.index)
    out['yaw_rate_pred_rads'] = sim_df['yaw_rate_pred_rads'].astype(float)
    return out

train, dev = split(dev_fraction=0.25, seed=42)
print('V0 baseline:')
r0 = score(v0)
print(f'  ALL FORD: yaw={r0["yaw_rate_rmse"]:.6f}  CTE={r0["cte_rmse"]:.3f}')
for k, v in r0['per_platform'].items():
    print(f'    {k}: yaw={v["yaw_rate_rmse"]:.6f}  CTE={v["cte_rmse"]:.3f}')

r0_dev = score(v0, segment_paths=dev)
print(f'  DEV ONLY: yaw={r0_dev["yaw_rate_rmse"]:.6f}  CTE={r0_dev["cte_rmse"]:.3f}')

print()
report('V1 — DEV (held-out)', paths=dev)
print()
report('V1 — ALL FORD', paths=None)
