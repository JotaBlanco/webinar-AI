"""Validate predict() against sim-only inputs (grader-shaped)."""
import sys, glob
sys.path.insert(0,'/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-05/final-model')
import pandas as pd
from predict import predict

pattern = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-05/data/sim-only/segments/*/*/*/*/sim.csv'
for p in glob.glob(pattern)[:4]:
    plat = p.split('segments/')[1].split('/')[0]
    df = pd.read_csv(p)
    pred = predict(df, plat)
    assert pred.index.equals(df.index)
    assert set(['yaw_rate_pred_rads','x_m','y_m']).issubset(pred.columns)
    print(f"OK {plat}: shape={pred.shape} cols={list(pred.columns)}")
