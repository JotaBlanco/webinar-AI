"""Verify predict() doesn't crash on sim-only data (the grading schema)."""
import sys, glob
sys.path.insert(0, '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-08/final-model')
from predict import predict
import pandas as pd
import numpy as np

for plat in ['TESLA_MODEL_3','HYUNDAI_IONIQ_5','FORD_MUSTANG_MACH_E_MK1','FORD_F_150_LIGHTNING_MK1']:
    files = sorted(glob.glob(f'/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-08/data/sim-only/segments/{plat}/*/*/*/sim.csv'))
    df = pd.read_csv(files[0])
    out = predict(df, plat)
    assert len(out) == len(df), 'length mismatch'
    assert (out.index == df.index).all()
    assert 'yaw_rate_pred_rads' in out.columns
    print(f'{plat}: OK n={len(out)} yr_range=[{out.yaw_rate_pred_rads.min():.3f},{out.yaw_rate_pred_rads.max():.3f}]')
    # compare to provided V0 baseline
    v0 = df['yaw_rate_pred_rads'].values
    diff = (out.yaw_rate_pred_rads.values - v0)
    print(f'   diff vs V0 baseline:  mean={diff.mean():.5f}  rms={np.sqrt((diff**2).mean()):.5f}')
