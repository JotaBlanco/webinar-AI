import sys, glob
sys.path.insert(0, "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-07/final-model")
import pandas as pd
from predict import predict

for plat in ["TESLA_MODEL_3","FORD_MUSTANG_MACH_E_MK1","FORD_F_150_LIGHTNING_MK1","HYUNDAI_IONIQ_5","UNKNOWN"]:
    pat = f"/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-07/data/sim-only/segments/{plat if plat!='UNKNOWN' else 'TESLA_MODEL_3'}/*/*/*/sim.csv"
    fs = sorted(glob.glob(pat))
    if not fs: continue
    d = pd.read_csv(fs[0])
    out = predict(d, plat)
    print(plat, "in_cols=", len(d.columns), "out_cols=", list(out.columns),
          "aligned=", (out.index==d.index).all(), "shape=", out.shape)
