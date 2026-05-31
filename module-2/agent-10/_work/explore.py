"""Quick exploration of segment counts and baseline metrics."""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from collections import Counter

ROOT = Path('/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-10')
sys.path.insert(0, str(ROOT / '_shared'))
from traj_metrics import cte_rmse_segment  # noqa: E402

paths = sorted((ROOT / 'data/sim/segments').glob('FORD_*/**/sim.csv'))
print('n_segments', len(paths))
c = Counter(p.resolve().parents[3].name for p in paths)
print('per platform', c)

# Sample one CSV to check columns/dt
df = pd.read_csv(paths[0])
print('cols', list(df.columns))
print('len', len(df), 'dt range', np.diff(df['t_s'].values).min(), np.diff(df['t_s'].values).max())
print('v range', df['v_mps'].min(), df['v_mps'].max())
print('delta_road_rad sample', df['delta_road_rad'].head().tolist())
print('delta_wheel_deg sample', df['delta_wheel_deg'].head().tolist())
