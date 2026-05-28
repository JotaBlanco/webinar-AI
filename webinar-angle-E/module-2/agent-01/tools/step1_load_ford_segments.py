#!/usr/bin/env python3
"""step1_load_ford_segments.py — collect Ford sim.csv files and load into one DataFrame."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
import pandas as pd

REQUIRED = {"t_s", "delta_road_rad", "v_mps",
            "yaw_rate_meas_rads", "yaw_rate_pred_rads", "yaw_rate_resid_rads"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", required=True,
                    choices=["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"])
    ap.add_argument("--data-root", default="data/sim/segments", type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    root = args.data_root / args.platform
    csvs = sorted(root.rglob("sim.csv"))
    if not csvs:
        print(f"no sim.csv under {root}", file=sys.stderr)
        return 1
    frames = []
    for p in csvs:
        df = pd.read_csv(p)
        missing = REQUIRED - set(df.columns)
        if missing:
            print(f"{p}: missing {missing}", file=sys.stderr)
            return 1
        df["__source__"] = str(p)
        frames.append(df)
    out_df = pd.concat(frames, ignore_index=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_parquet(args.out)
    print(f"loaded {len(csvs)} segments, {len(out_df)} rows → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
