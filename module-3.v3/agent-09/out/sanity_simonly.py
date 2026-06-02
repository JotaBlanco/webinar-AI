"""Verify final-model/predict.py runs against sim-only (no truth) — does not error."""
from __future__ import annotations
import sys
import importlib.util
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("final_predict", ROOT / "final-model" / "predict.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

n_ok = 0; n_fail = 0
sim_only = ROOT / "data" / "sim-only" / "segments"
for plat_dir in sorted(sim_only.iterdir()):
    if not plat_dir.is_dir(): continue
    plat = plat_dir.name
    for p in list(plat_dir.glob("**/sim.csv"))[:3]:  # sample 3 per platform
        try:
            df = pd.read_csv(p)
            out = m.predict(df, plat)
            assert "yaw_rate_pred_rads" in out.columns
            assert len(out) == len(df)
            n_ok += 1
        except Exception as e:
            n_fail += 1
            print(f"FAIL {plat} {p.name}: {e}")
print(f"sim-only sanity: {n_ok} ok, {n_fail} fail")
