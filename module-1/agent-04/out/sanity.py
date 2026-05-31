"""Quick smoke test of predict against a sim-only segment."""
import sys, glob, pandas as pd, numpy as np
sys.path.insert(0, '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-04/final-model')
from predict import predict

INPUT_COLS = ['t_s','delta_wheel_deg','delta_road_rad','v_mps','a_long_mps2',
              'accel_pedal_pct','brake_pressed','yaw_rate_pred_rads']

for plat in ['TESLA_MODEL_3','FORD_F_150_LIGHTNING_MK1','FORD_MUSTANG_MACH_E_MK1','HYUNDAI_IONIQ_5']:
    files = sorted(glob.glob(f'/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-04/data/sim-only/segments/{plat}/*/*/*/sim.csv'))
    f = files[0]
    sim_in = pd.read_csv(f)[INPUT_COLS]
    out = predict(sim_in.copy(), plat)
    assert list(out.columns) == ['yaw_rate_pred_rads','x_m','y_m'], out.columns
    assert len(out) == len(sim_in)
    print(f"{plat}: predict OK on {len(sim_in)} rows. yaw range: [{out['yaw_rate_pred_rads'].min():.3f}, {out['yaw_rate_pred_rads'].max():.3f}]")
print("\nAll platforms predict() smoke-test passed.")
