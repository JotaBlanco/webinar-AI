import sys, os
sys.path.insert(0, '/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-01')
sys.path.insert(0, '/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-01/skills/score-model')
os.chdir('/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-01')
from score import score
import pandas as pd

def v0(sim_df, platform):
    return pd.DataFrame({'yaw_rate_pred_rads': sim_df['yaw_rate_pred_rads'].values}, index=sim_df.index)

res = score(v0)
print('V0 overall yaw RMSE:', res['yaw_rate_rmse'])
print('V0 overall CTE  RMSE:', res['cte_rmse'])
print('n_segments:', res['n_segments'], 'failed:', res['failed_segments'])
print('per_platform:')
for k,v in res['per_platform'].items():
    print(' ', k, v)
print('per_regime:', res['per_regime'])
