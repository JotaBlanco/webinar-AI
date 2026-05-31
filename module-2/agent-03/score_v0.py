"""Score the V0 baseline."""
import sys
sys.path.insert(0, 'skills/score-model')
from score import score
import pandas as pd

def predict_v0(sim_df, platform):
    return pd.DataFrame(
        {'yaw_rate_pred_rads': sim_df['yaw_rate_pred_rads'].values},
        index=sim_df.index,
    )

result = score(predict_v0)
print('V0 baseline:')
print('  yaw RMSE:', result['yaw_rate_rmse'])
print('  CTE RMSE:', result['cte_rmse'])
print('  n_segments:', result['n_segments'])
print('  n_samples:', result['n_samples'])
for k, v in result['per_platform'].items():
    print('  ', k, 'yr:', v['yaw_rate_rmse'], 'cte:', v['cte_rmse'], 'n_seg:', v['n_segments'])
print('  regime:', result['per_regime'])
print('  failed:', result['failed_segments'])
