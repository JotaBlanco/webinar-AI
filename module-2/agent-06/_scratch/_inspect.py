import pandas as pd
import numpy as np
import glob

paths = sorted(glob.glob('/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-06/data/sim/segments/FORD_*/**/sim.csv', recursive=True))
print(f'total Ford segments: {len(paths)}')
df = pd.read_csv(paths[0])
print('columns:', list(df.columns))
print('shape:', df.shape)
print('v range:', df.v_mps.min(), df.v_mps.max())
print('delta_road range:', df.delta_road_rad.min(), df.delta_road_rad.max())
print('yaw truth range:', df.yaw_rate_meas_rads.min(), df.yaw_rate_meas_rads.max())
print('yaw pred range:', df.yaw_rate_pred_rads.min(), df.yaw_rate_pred_rads.max())
print('dt typical:', np.median(np.diff(df.t_s.values)))
print('first segment path:', paths[0])
print('seg len mean/median:', np.mean([pd.read_csv(p).shape[0] for p in paths[:5]]))
