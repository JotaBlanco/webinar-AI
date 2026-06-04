"""Score the shipped final-model on sim/ data (with truth) and check sim-only contract.

The grader uses sim-only (no truth, no extras). We can't score against sim-only
because there's no truth, but we run our predict on sim-only segments to verify
no KeyError, and we score against sim/ (where truth lives) to get the final KPIs.
"""
import os, sys
import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-03")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "final-model"))

from score import score, format_summary
import predict as predict_mod

def predict_wrapper(sim_df, platform):
    return predict_mod.predict(sim_df, platform)

r = score(predict_wrapper)
print(format_summary(r, top_n=5))
print(f"\nHEADLINE: yaw_rate_rmse={r['yaw_rate_rmse']:.6f}  cte_rmse={r['cte_rmse']:.4f}")

# Sanity: also try sim-only paths (no truth) to confirm no KeyError on predict
print("\n--- sim-only contract check ---")
so_root = ROOT / "data" / "sim-only" / "segments"
sample = next(so_root.glob("FORD_MUSTANG_MACH_E_MK1/*/*/*/sim.csv"))
df = pd.read_csv(sample)
print(f"sim-only sample: {sample.relative_to(ROOT)}")
print(f"sim-only columns: {list(df.columns)}")
out = predict_wrapper(df, "FORD_MUSTANG_MACH_E_MK1")
print(f"predict output shape: {out.shape}, NaN count: {out['yaw_rate_pred_rads'].isna().sum()}")

# Try all 4 platforms
for plat in ["TESLA_MODEL_3", "FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]:
    samp = next(so_root.glob(f"{plat}/*/*/*/sim.csv"), None)
    if samp is None: continue
    df = pd.read_csv(samp)
    o = predict_wrapper(df, plat)
    print(f"  {plat}: rows={len(o)} nan={o['yaw_rate_pred_rads'].isna().sum()} ok")
