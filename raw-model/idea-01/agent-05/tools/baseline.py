"""Compute baseline lateral prediction error from existing Ford sim CSVs.

Primary metric: RMSE of yaw_rate_pred vs yaw_rate_meas (rad/s), pooled across
all available Ford segments. Secondary: RMSE of a_y_pred vs a_lat_meas.
Only Ford has measured truth channels (Tesla rlogs lack IMU decoding).
"""
from __future__ import annotations

import glob
import os
import sys

import numpy as np
import pandas as pd

DATA_ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-05/data/sim/segments"


def find_ford_csvs():
    paths = []
    for plat in ("FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"):
        paths.extend(glob.glob(os.path.join(DATA_ROOT, plat, "**", "sim.csv"),
                               recursive=True))
    return sorted(paths)


def load_and_stack(paths):
    rows = []
    for p in paths:
        try:
            df = pd.read_csv(p)
        except Exception as e:
            print(f"skip {p}: {e}", file=sys.stderr)
            continue
        needed = {"yaw_rate_pred_rads", "yaw_rate_meas_rads",
                  "a_y_pred_mps2", "a_lat_meas_mps2"}
        if not needed.issubset(df.columns):
            continue
        plat = "MACH_E" if "MACH_E" in p else "F150"
        df["__platform"] = plat
        df["__path"] = p
        rows.append(df)
    if not rows:
        raise RuntimeError("no Ford sim CSVs found")
    return pd.concat(rows, ignore_index=True)


def rmse(a, b):
    return float(np.sqrt(np.mean((a - b) ** 2)))


def mae(a, b):
    return float(np.mean(np.abs(a - b)))


def report(df):
    y_pred = df["yaw_rate_pred_rads"].to_numpy()
    y_meas = df["yaw_rate_meas_rads"].to_numpy()
    a_pred = df["a_y_pred_mps2"].to_numpy()
    a_meas = df["a_lat_meas_mps2"].to_numpy()
    print(f"  n={len(df):>7d} samples across "
          f"{df['__path'].nunique()} segments")
    print(f"  yaw_rate RMSE = {rmse(y_pred, y_meas):.5f} rad/s")
    print(f"  yaw_rate MAE  = {mae(y_pred, y_meas):.5f} rad/s")
    print(f"  a_y      RMSE = {rmse(a_pred, a_meas):.5f} m/s²")
    return rmse(y_pred, y_meas), rmse(a_pred, a_meas)


if __name__ == "__main__":
    paths = find_ford_csvs()
    print(f"Found {len(paths)} Ford sim CSVs")
    df = load_and_stack(paths)
    print("\n=== Pooled baseline ===")
    report(df)
    print("\n=== Per platform ===")
    for plat in df["__platform"].unique():
        print(f"-- {plat}")
        report(df[df["__platform"] == plat])
