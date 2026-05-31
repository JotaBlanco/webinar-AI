"""Score V0 baseline."""
import sys
sys.path.insert(0, 'skills/score-model')
import pandas as pd
from score import score


def predict_v0(sim_df, platform):
    return pd.DataFrame({'yaw_rate_pred_rads': sim_df['yaw_rate_pred_rads'].values}, index=sim_df.index)


r = score(predict_v0)
print('V0 Baseline:')
print('  Yaw RMSE:', r['yaw_rate_rmse'])
print('  CTE RMSE:', r['cte_rmse'])
print('  Segments:', r['n_segments'])
for plat, pr in r['per_platform'].items():
    print(f'  {plat}: yaw={pr["yaw_rate_rmse"]:.5f} cte={pr["cte_rmse"]:.4f}  n_seg={pr["n_segments"]}')
print('  Per-regime:', r['per_regime'])
print('  Failed:', r['failed_segments'])
