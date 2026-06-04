"""Smoke-test the final-model predict against sim-only segments — make sure it
doesn't raise KeyError on truth columns being absent."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-04")
sys.path.insert(0, str(ROOT / "final-model"))
from predict import predict  # noqa: E402

ok = 0
fail = 0
errs = []
for plat_dir in (ROOT / "data" / "sim-only" / "segments").iterdir():
    plat = plat_dir.name
    paths = sorted(plat_dir.glob("**/sim.csv"))
    for p in paths[:3]:
        df = pd.read_csv(p)
        try:
            out = predict(df, plat)
            assert "yaw_rate_pred_rads" in out.columns
            assert len(out) == len(df)
            assert not out["yaw_rate_pred_rads"].isna().any()
            ok += 1
        except Exception as e:
            fail += 1
            errs.append((plat, str(p), repr(e)))
print(f"ok={ok} fail={fail}")
for e in errs[:5]:
    print(e)
