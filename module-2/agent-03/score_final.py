"""Score the final-model predict() against all data; also separately on the dev split."""
import sys, importlib.util
sys.path.insert(0, 'skills/score-model')
sys.path.insert(0, 'final-model')
from score import score
import numpy as np

# load predict module
spec = importlib.util.spec_from_file_location('predict_mod', 'final-model/predict.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Full
result = score(mod.predict)
print('=== V1 (full data) ===')
print('  yaw RMSE:', result['yaw_rate_rmse'])
print('  CTE RMSE:', result['cte_rmse'])
print('  n_segments:', result['n_segments'])
for k, v in result['per_platform'].items():
    print(' ', k, 'yr:', v['yaw_rate_rmse'], 'cte:', v['cte_rmse'], 'n_seg:', v['n_segments'])
print('  per_regime:', result['per_regime'])

# Now per-platform on the dev set (the 20% held out during fit)
from pathlib import Path
np.random.seed(42)
for plat in ['FORD_F_150_LIGHTNING_MK1', 'FORD_MUSTANG_MACH_E_MK1']:
    paths = sorted(Path('data/sim/segments').glob(f'{plat}/**/sim.csv'))
    idxs = list(range(len(paths)))
    np.random.shuffle(idxs)
    n_train = int(0.8*len(paths))
    dev_paths = [paths[i] for i in idxs[n_train:]]
    res = score(mod.predict, segment_paths=dev_paths)
    print(f'\n=== V1 dev [{plat}] ===')
    print('  yaw RMSE:', res['yaw_rate_rmse'])
    print('  CTE RMSE:', res['cte_rmse'])
    print('  n_segments:', res['n_segments'])
