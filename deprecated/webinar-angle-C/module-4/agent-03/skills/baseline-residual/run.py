#!/usr/bin/env python3
"""baseline-residual/run.py — canonical V0 computation.

Mirrors `evals/baseline_rmse.py` exactly. Walks every sim.csv under
`data/sim/segments/<PLATFORM>/`, applies the regime mask, returns RMSE of
`yaw_rate_resid_rads` (no preprocessing).
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
        print("usage: run.py <PLATFORM>", file=sys.stderr)
        sys.exit(2)
    platform = sys.argv[1]
    data_root = Path("data/sim/segments") / platform
    if not data_root.is_dir():
        print(f"not a directory: {data_root}", file=sys.stderr)
        sys.exit(2)

    csvs = sorted(data_root.rglob("sim.csv"))
    frames = [pd.read_csv(p) for p in csvs]
    big = pd.concat(frames, ignore_index=True)
    reg = regime_mask(big)

    print(f"Platform: {platform}")
    print(f"Segments: {len(csvs)}")
    print(f"Samples:  {len(big)}")
    print(f"V0 RMSE on yaw_rate_resid_rads (rad/s):")
    print(f"  overall:   {rmse(big['yaw_rate_resid_rads']):.5f}  (n={len(big)})")
    for r in ("straight", "steady", "transient"):
        sub = big.loc[reg == r, "yaw_rate_resid_rads"]
        print(f"  {r:<10s}{rmse(sub):.5f}  (n={len(sub)})")


if __name__ == "__main__":
    main()
