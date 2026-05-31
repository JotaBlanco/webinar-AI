import sys, os
ROOT = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-01'
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'skills/score-model'))
sys.path.insert(0, os.path.join(ROOT, 'final-model'))
os.chdir(ROOT)
from score import score
from predict import predict as v2_predict
import pandas as pd

def v0(sim_df, platform):
    return pd.DataFrame({'yaw_rate_pred_rads': sim_df['yaw_rate_pred_rads'].values}, index=sim_df.index)

res0 = score(v0)
res2 = score(v2_predict)
print('V0 yaw RMSE:', res0['yaw_rate_rmse'], 'CTE:', res0['cte_rmse'])
print('V2 yaw RMSE:', res2['yaw_rate_rmse'], 'CTE:', res2['cte_rmse'])
print()
print('Per-platform V0:')
for k,v in res0['per_platform'].items(): print(' ', k, v)
print('Per-platform V2:')
for k,v in res2['per_platform'].items(): print(' ', k, v)
print()
print('Per-regime V0:', res0['per_regime'])
print('Per-regime V2:', res2['per_regime'])
