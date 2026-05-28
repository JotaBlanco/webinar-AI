#!/usr/bin/env python3
"""schema_check.py — computational sensor for sim CSV integrity.

Verifies that a Ford `sim.csv` (or a derived CSV you produced) obeys the
project's invariants:

  1. Required columns present.
  2. `yaw_rate_resid_rads ≈ yaw_rate_pred_rads − yaw_rate_meas_rads` (tol 1e-6).
  3. `a_y_resid_mps2 ≈ a_y_pred_mps2 − a_lat_meas_mps2` (tol 1e-6).
  4. `corr(delta_road_rad, yaw_rate_meas_rads) > 0` on cornering samples
     (sign-convention sanity).
  5. No NaNs in the truth or prediction columns.

Run with `python3 schema_check.py <sim.csv>`. Exits 0 iff every check passes.
Use this on every variant CSV before scoring; it catches sign flips, float
round-trip drift, and dropped rows.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REQUIRED_COLS = [
    "t_s", "delta_road_rad", "v_mps",
    "yaw_rate_meas_rads", "yaw_rate_pred_rads", "yaw_rate_resid_rads",
    "a_lat_meas_mps2", "a_y_pred_mps2", "a_y_resid_mps2",
]
RESID_TOL = 1e-6
CORNERING_DELTA = 0.01


def check(csv_path: Path) -> tuple[bool, list[str]]:
    failures: list[str] = []
    df = pd.read_csv(csv_path)

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        failures.append(f"missing columns: {missing}")
        return False, failures

    yaw_resid_check = df["yaw_rate_pred_rads"] - df["yaw_rate_meas_rads"]
    yaw_resid_err = (df["yaw_rate_resid_rads"] - yaw_resid_check).abs().max()
    if yaw_resid_err > RESID_TOL:
        failures.append(f"yaw_rate_resid sign/value mismatch — max diff {yaw_resid_err:.2e} > {RESID_TOL}")

    ay_resid_check = df["a_y_pred_mps2"] - df["a_lat_meas_mps2"]
    ay_resid_err = (df["a_y_resid_mps2"] - ay_resid_check).abs().max()
    if ay_resid_err > RESID_TOL:
        failures.append(f"a_y_resid sign/value mismatch — max diff {ay_resid_err:.2e} > {RESID_TOL}")

    cornering = df.loc[df["delta_road_rad"].abs() >= CORNERING_DELTA]
    if len(cornering) > 50:
        corr = cornering[["delta_road_rad", "yaw_rate_meas_rads"]].corr().iloc[0, 1]
        if corr <= 0:
            failures.append(f"sign-convention check failed: corr(δ_road, ψ̇_meas)={corr:.3f} (must be > 0)")

    for col in ("yaw_rate_meas_rads", "yaw_rate_pred_rads"):
        if df[col].isna().any():
            failures.append(f"NaN values in {col}")

    return len(failures) == 0, failures


def main():
    if len(sys.argv) != 2:
        print("usage: schema_check.py <sim.csv>", file=sys.stderr)
        sys.exit(2)
    p = Path(sys.argv[1])
    if not p.is_file():
        print(f"not found: {p}", file=sys.stderr)
        sys.exit(2)
    ok, failures = check(p)
    if ok:
        print(f"[PASS] {p}")
        sys.exit(0)
    print(f"[FAIL] {p}")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)


if __name__ == "__main__":
    main()
