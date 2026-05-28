#!/usr/bin/env python3
"""baseline_rmse.py — canonical V0 baseline RMSE on a Ford platform.

Computes the V0 baseline (i.e. RMSE on `yaw_rate_resid_rads` as-is, with no
preprocessing) across all sim CSVs for a given platform, broken out by regime.
Use this as the reference number every variant should beat; if your "before"
RMSE doesn't match this, your scoring code has a bug.

Run with `python3 baseline_rmse.py <PLATFORM>` where `<PLATFORM>` is one of
`FORD_MUSTANG_MACH_E_MK1` or `FORD_F_150_LIGHTNING_MK1`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REGIME_DELTA_THR = 0.01
REGIME_DDELTA_THR = 0.05


def regime_mask(df: pd.DataFrame) -> pd.Series:
    delta = df["delta_road_rad"].to_numpy()
    t = df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    dt = np.where(dt <= 0, 0.02, dt)
    ddelta = np.gradient(delta) / dt
    out = np.full(len(df), "transient", dtype=object)
    out[np.abs(delta) < REGIME_DELTA_THR] = "straight"
    steady = (np.abs(delta) >= REGIME_DELTA_THR) & (np.abs(ddelta) < REGIME_DDELTA_THR)
    out[steady] = "steady"
    return pd.Series(out, index=df.index, name="regime")


def rmse(arr) -> float:
    s = np.asarray(arr, dtype=float)
    s = s[np.isfinite(s)]
    return float(np.sqrt(np.mean(s ** 2))) if s.size else float("nan")


def main():
    if len(sys.argv) != 2:
        print("usage: baseline_rmse.py <PLATFORM>", file=sys.stderr)
        sys.exit(2)
    platform = sys.argv[1]

    data_root = Path("data/sim/segments") / platform
    if not data_root.is_dir():
        print(f"not a directory: {data_root}", file=sys.stderr)
        sys.exit(2)

    csvs = sorted(data_root.rglob("sim.csv"))
    if not csvs:
        print(f"no sim.csv under {data_root}", file=sys.stderr)
        sys.exit(2)

    frames = []
    for p in csvs:
        df = pd.read_csv(p)
        df["__source__"] = str(p)
        frames.append(df)
    big = pd.concat(frames, ignore_index=True)

    reg = regime_mask(big)
    overall = rmse(big["yaw_rate_resid_rads"])
    by_regime = {r: rmse(big.loc[reg == r, "yaw_rate_resid_rads"]) for r in ("straight", "steady", "transient")}

    print(f"Platform: {platform}")
    print(f"Segments: {len(csvs)}")
    print(f"Samples:  {len(big)}")
    print(f"V0 baseline RMSE on yaw_rate_resid_rads (rad/s):")
    print(f"  overall:   {overall:.5f}")
    for r in ("straight", "steady", "transient"):
        print(f"  {r:<10s}{by_regime[r]:.5f}")


if __name__ == "__main__":
    main()
