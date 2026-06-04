"""Smoke check: run predict against a sim-only csv (grader's contract)."""
import sys
from pathlib import Path
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-08")
sys.path.insert(0, str(ROOT / "final-model"))
from predict import predict

for plat in ("FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5", "TESLA_MODEL_3"):
    root = ROOT / "data" / "sim-only" / "segments" / plat
    paths = sorted(root.glob("**/sim.csv"))
    if not paths:
        print(f"{plat}: no sim-only segments")
        continue
    p = paths[0]
    df = pd.read_csv(p)
    out = predict(df, plat)
    assert "yaw_rate_pred_rads" in out.columns
    assert len(out) == len(df)
    print(f"{plat}: cols={list(df.columns)[:4]}... → {len(out)} rows OK, "
          f"yr range [{out['yaw_rate_pred_rads'].min():.4f}, {out['yaw_rate_pred_rads'].max():.4f}]")
