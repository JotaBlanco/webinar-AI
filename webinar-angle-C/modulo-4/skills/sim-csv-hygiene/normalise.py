"""Recompute residual columns from `meas − pred` at full precision. See SKILL.md.

Usage:
    python skills/sim-csv-hygiene/normalise.py <sim-dir>
"""
import sys
from pathlib import Path

import pandas as pd


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    d = Path(sys.argv[1])
    csvs = sorted(d.rglob("*.csv"))
    n = 0
    for c in csvs:
        df = pd.read_csv(c)
        if {"yaw_rate_meas_rads", "yaw_rate_pred_rads"}.issubset(df.columns):
            df["yaw_rate_resid_rads"] = df["yaw_rate_meas_rads"] - df["yaw_rate_pred_rads"]
        if {"a_lat_meas_mps2", "a_y_pred_mps2"}.issubset(df.columns):
            df["a_y_resid_mps2"] = df["a_lat_meas_mps2"] - df["a_y_pred_mps2"]
        df.to_csv(c, index=False, float_format="%.10g")
        n += 1
    print(f"normalised {n} CSV(s) under {d}")


if __name__ == "__main__":
    main()
