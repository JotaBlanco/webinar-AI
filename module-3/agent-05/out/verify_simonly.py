"""Verify predict() works against sim-only mirror (canonical input contract)."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-05")
sys.path.insert(0, str(ROOT / "final-model"))
from predict import predict

seg_root = ROOT / "data" / "sim-only" / "segments"
paths = sorted(p for p in seg_root.glob("*/**/sim.csv") if p.is_file())
print(f"sim-only segments: {len(paths)}")

# Run on one segment per platform
platforms_seen = {}
for p in paths:
    plat = p.resolve().parents[3].name
    if plat in platforms_seen:
        continue
    platforms_seen[plat] = p

for plat, p in platforms_seen.items():
    df = pd.read_csv(p)
    print(f"\n{plat}: cols={list(df.columns)}")
    try:
        out = predict(df, plat)
        print(f"  -> ok, len={len(out)}, mean yr_pred={out['yaw_rate_pred_rads'].mean():.5f}")
    except Exception as e:
        print(f"  -> FAILED: {type(e).__name__}: {e}")
