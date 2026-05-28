#!/usr/bin/env python3
"""step3_compute_residuals.py — V0 per-regime RMSE on yaw_rate_resid_rads (no preprocessing)."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd


def rmse(arr):
    a = np.asarray(arr, dtype=float)
    a = a[np.isfinite(a)]
    return float("nan") if a.size == 0 else float(np.sqrt(np.mean(a ** 2)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    df = pd.read_parquet(args.inp)
    r = df["yaw_rate_resid_rads"].to_numpy()
    out = {"V0_overall": rmse(r)}
    for reg in ("straight", "steady", "transient"):
        out[f"V0_{reg}"] = rmse(df.loc[df["regime"] == reg, "yaw_rate_resid_rads"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2))
    print(f"V0 RMSE → {args.out}: overall={out['V0_overall']:.5f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
