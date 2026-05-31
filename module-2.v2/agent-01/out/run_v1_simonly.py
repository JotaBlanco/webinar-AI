"""Sanity test: run predict against sim-only inputs to confirm grading-time works.
We cannot score (no truth) but we verify predict succeeds on every sim-only segment.
"""
import glob, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "final-model"))
import pandas as pd
from predict import predict

paths = sorted(glob.glob(str(ROOT / "data" / "sim-only" / "segments" / "*" / "**" / "sim.csv"), recursive=True))
print(f"{len(paths)} sim-only segments")
ok = bad = 0
import numpy as np
for p in paths:
    df = pd.read_csv(p)
    plat = Path(p).resolve().parents[3].name
    try:
        out = predict(df, plat)
        assert isinstance(out, pd.DataFrame)
        assert "yaw_rate_pred_rads" in out.columns
        assert len(out) == len(df)
        assert not np.any(np.isnan(out["yaw_rate_pred_rads"].to_numpy()))
        ok += 1
    except Exception as e:
        bad += 1
        if bad <= 3:
            print(f"FAIL {p}: {e}")
print(f"OK={ok}  BAD={bad}")
