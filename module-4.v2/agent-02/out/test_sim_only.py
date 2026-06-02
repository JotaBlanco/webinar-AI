"""Verify predict() works against sim-only/segments/ (grader-mirrored contract)."""
from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-02")
sys.path.insert(0, str(ROOT / "final-model"))
from predict import predict  # noqa: E402

paths = sorted((ROOT / "data" / "sim-only" / "segments").glob("*/*/*/*/sim.csv"))[:5]
for p in paths:
    df = pd.read_csv(p)
    platform = p.resolve().parents[3].name
    print(f"{platform}: cols={list(df.columns)}, n={len(df)}")
    out = predict(df, platform)
    print(f"  predict OK, rows={len(out)}, has_yaw={out.columns.tolist()}")
