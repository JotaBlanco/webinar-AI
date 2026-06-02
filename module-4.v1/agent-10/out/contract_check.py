"""Verify predict() works on a sim-only segment (input-only mirror)."""
import sys
from pathlib import Path
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-10")
sys.path.insert(0, str(ROOT / "final-model"))
from predict import predict

# Get one segment per platform from sim-only
SO = ROOT / "data" / "sim-only" / "segments"
for platform in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5", "TESLA_MODEL_3"]:
    paths = list((SO / platform).glob("*/*/*/sim.csv"))
    if not paths:
        print(f"{platform}: NO sim-only segments")
        continue
    p = paths[0]
    df = pd.read_csv(p)
    print(f"\n{platform} ({p.name}) cols: {list(df.columns)}")
    try:
        out = predict(df, platform)
        print(f"  predict OK shape={out.shape} cols={list(out.columns)}")
        print(f"  first 3 yaw_rate_pred_rads: {out['yaw_rate_pred_rads'].head(3).tolist()}")
    except Exception as e:
        print(f"  predict FAILED: {type(e).__name__}: {e}")
