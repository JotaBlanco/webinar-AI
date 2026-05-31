"""Score the actual final-model/predict.py bundle against full Ford eval."""
import sys, importlib.util
from pathlib import Path
sys.path.insert(0, 'skills/score-model')
from score import score

bundle = Path('final-model').resolve()
sys.path.insert(0, str(bundle))
spec = importlib.util.spec_from_file_location('bundle_predict', str(bundle / 'predict.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
predict_fn = mod.predict

import pandas as pd
def v0(sim_df, platform):
    out = pd.DataFrame(index=sim_df.index)
    out['yaw_rate_pred_rads'] = sim_df['yaw_rate_pred_rads']
    return out

r0 = score(v0)
rf = score(predict_fn)
print(f'V0:        yaw_rmse={r0["yaw_rate_rmse"]:.5f}  cte_rmse={r0["cte_rmse"]:.3f}  n_seg={r0["n_segments"]}')
print(f'V_final:   yaw_rmse={rf["yaw_rate_rmse"]:.5f}  cte_rmse={rf["cte_rmse"]:.3f}  n_seg={rf["n_segments"]} failed={rf["failed_segments"]}')
print('per_platform:')
for plat in r0['per_platform']:
    a = r0['per_platform'][plat]; b = rf['per_platform'][plat]
    print(f'  {plat}: V0 yr={a["yaw_rate_rmse"]:.5f} cte={a["cte_rmse"]:.2f}  →  Vf yr={b["yaw_rate_rmse"]:.5f} cte={b["cte_rmse"]:.2f}')
print('per_regime:', rf['per_regime'])
