"""Sanity-check: predict() must succeed on sim-only/segments/ (the input-only
mirror handed to predict at grading time, which lacks truth columns)."""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-07")
sys.path.insert(0, str(ROOT / "final-model"))
from predict import predict, PLATFORM_SUPPORT  # noqa

seg_root = ROOT / "data" / "sim-only" / "segments"
paths = sorted(p for p in seg_root.glob("*/**/sim.csv") if p.is_file())
print(f"found {len(paths)} sim-only segments")
n_ok = 0
n_fail = 0
fail_examples = []
for p in paths:
    plat = p.resolve().parents[3].name
    df = pd.read_csv(p)
    try:
        out = predict(df, plat)
        assert "yaw_rate_pred_rads" in out.columns
        assert len(out) == len(df)
        n_ok += 1
    except Exception as e:
        n_fail += 1
        if len(fail_examples) < 3:
            fail_examples.append((str(p), type(e).__name__, str(e)))

print(f"ok={n_ok} fail={n_fail}")
for f in fail_examples:
    print(f)
print("platform_support:", PLATFORM_SUPPORT)
