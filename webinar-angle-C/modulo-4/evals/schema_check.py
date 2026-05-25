"""Computational sensor — Ford sim CSV schema + sanity.

Runs in milliseconds. The deal with the agent: if this fails on your generated
CSV, your variant is invalid and your ablation row is not allowed in the report.

Usage:
    python evals/schema_check.py <csv-or-dir>
    # exits 0 if all CSVs pass, non-zero otherwise.
"""
import math
import sys
from pathlib import Path

import pandas as pd

REQUIRED_COLS = {
    "t_s",
    "delta_wheel_deg",
    "delta_road_rad",
    "v_mps",
    "a_long_mps2",
    "a_lat_meas_mps2",
    "yaw_rate_meas_rads",
    "x_m",
    "y_m",
    "psi_rad",
    "v_state_mps",
    "delta_state_rad",
    "yaw_rate_pred_rads",
    "a_y_pred_mps2",
    "yaw_rate_resid_rads",
    "a_y_resid_mps2",
}

# Loose physical bounds — values outside are almost certainly bugs.
BOUNDS = {
    "v_mps": (-5.0, 70.0),                 # ≤ ~250 km/h
    "delta_road_rad": (-1.2, 1.2),         # ≤ ~70°
    "a_long_mps2": (-15.0, 15.0),
    "a_lat_meas_mps2": (-25.0, 25.0),      # ≤ ~2.5 g
    "yaw_rate_meas_rads": (-3.0, 3.0),     # ≤ ~170 °/s
    "yaw_rate_pred_rads": (-3.0, 3.0),
    "a_y_pred_mps2": (-25.0, 25.0),
}


def check_csv(path: Path) -> list[str]:
    errors = []
    df = pd.read_csv(path)
    missing = REQUIRED_COLS - set(df.columns)
    if missing:
        errors.append(f"missing columns: {sorted(missing)}")
        return errors  # cannot do bound checks reliably without columns
    if df.empty:
        errors.append("empty CSV")
        return errors
    nan_cols = [c for c in REQUIRED_COLS if df[c].isna().any()]
    if nan_cols:
        errors.append(f"NaNs in required columns: {nan_cols}")
    # Residual sign check: resid should equal meas - pred (within tolerance)
    yaw_check = (df["yaw_rate_resid_rads"] - (df["yaw_rate_meas_rads"] - df["yaw_rate_pred_rads"])).abs().max()
    if yaw_check > 1e-6:
        errors.append(f"yaw_rate_resid sign wrong (max diff {yaw_check:.2e}) — convention is meas − pred")
    a_check = (df["a_y_resid_mps2"] - (df["a_lat_meas_mps2"] - df["a_y_pred_mps2"])).abs().max()
    if a_check > 1e-6:
        errors.append(f"a_y_resid sign wrong (max diff {a_check:.2e}) — convention is meas − pred")
    # Physical bounds
    for col, (lo, hi) in BOUNDS.items():
        col_min, col_max = df[col].min(), df[col].max()
        if col_min < lo or col_max > hi:
            errors.append(f"{col} out of physical bounds [{lo}, {hi}] — actual [{col_min:.3f}, {col_max:.3f}]")
    # Time monotone
    if not df["t_s"].is_monotonic_increasing:
        errors.append("t_s not monotonically increasing")
    # Reasonable sampling
    if len(df) > 1:
        dt = df["t_s"].diff().dropna()
        if not (0.005 < dt.median() < 0.05):
            errors.append(f"unexpected sampling: median dt = {dt.median():.4f}s (expected ~0.02 for 50 Hz)")
    return errors


def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    target = Path(sys.argv[1])
    if target.is_dir():
        paths = sorted(target.rglob("*.csv"))
    else:
        paths = [target]
    if not paths:
        print(f"no CSVs found under {target}", file=sys.stderr)
        sys.exit(2)
    failed = 0
    for p in paths:
        errs = check_csv(p)
        if errs:
            failed += 1
            print(f"FAIL {p}")
            for e in errs:
                print(f"  - {e}")
        else:
            print(f"PASS {p}")
    if failed:
        print(f"\n{failed}/{len(paths)} CSVs failed.")
        sys.exit(1)
    print(f"\nAll {len(paths)} CSVs passed.")


if __name__ == "__main__":
    main()
