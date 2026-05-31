"""Score the final-model/predict.py against all Ford segments."""
import sys
sys.path.insert(0, 'skills/score-model')
sys.path.insert(0, 'final-model')
import pandas as pd
from score import score
from predict import predict

r = score(predict)
print('FINAL MODEL:')
print(f'  Yaw RMSE: {r["yaw_rate_rmse"]:.6f}')
print(f'  CTE RMSE: {r["cte_rmse"]:.4f}')
print(f'  Segments: {r["n_segments"]}')
for plat, pr in r['per_platform'].items():
    print(f'  {plat}: yaw={pr["yaw_rate_rmse"]:.5f}  cte={pr["cte_rmse"]:.4f}  n_seg={pr["n_segments"]}')
print('  Per-regime:')
for k, v in r['per_regime'].items():
    print(f'    {k}: yaw_rmse={v["yaw_rate_rmse"]:.5f}  n_samples={v["n_samples"]}')
print(f'  Failed: {r["failed_segments"]}')

# Compare side-by-side to V0
def predict_v0(sim_df, platform):
    return pd.DataFrame({'yaw_rate_pred_rads': sim_df['yaw_rate_pred_rads'].values}, index=sim_df.index)
r0 = score(predict_v0)
print('\nV0 BASELINE (for comparison):')
print(f'  Yaw RMSE: {r0["yaw_rate_rmse"]:.6f}')
print(f'  CTE RMSE: {r0["cte_rmse"]:.4f}')
print('\nDELTAS:')
print(f'  Yaw RMSE: {r["yaw_rate_rmse"] - r0["yaw_rate_rmse"]:+.6f}  ({100*(r["yaw_rate_rmse"]-r0["yaw_rate_rmse"])/r0["yaw_rate_rmse"]:+.1f}%)')
print(f'  CTE RMSE: {r["cte_rmse"] - r0["cte_rmse"]:+.4f}  ({100*(r["cte_rmse"]-r0["cte_rmse"])/r0["cte_rmse"]:+.1f}%)')
