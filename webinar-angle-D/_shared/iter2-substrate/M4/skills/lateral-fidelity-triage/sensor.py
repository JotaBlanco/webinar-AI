#!/usr/bin/env python3
"""sensor.py — one-shot computational regression guard for the lateral-fidelity-triage skill.

Loads a CSV with at least `yaw_rate_pred_rads` and `yaw_rate_meas_rads` columns
and checks two deterministic properties of a candidate "best variant":

  1. Sign consistency  — corr(pred, meas) > 0 on the cornering subset.
                          A sign flip makes RMSE look small while the variant is
                          unshippable.
  2. No-worse-than-V0  — RMSE(pred − meas) ≤ baseline RMSE.
                          Baseline is the RMSE of `yaw_rate_resid_rads` if that
                          column is present, else the RMSE of (pred − meas) of
                          the un-recalibrated KS, which the caller should supply
                          via --baseline-rmse.

Exit code 0 if both pass; 1 if either fails. Prints a one-liner either way.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd


REGIME_DELTA_THR = 0.01  # rad — same threshold as the skill's regime mask.


def rmse(arr: np.ndarray) -> float:
    arr = arr[np.isfinite(arr)]
    return float("nan") if arr.size == 0 else float(np.sqrt(np.mean(arr ** 2)))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("csv", type=Path, help="CSV with yaw_rate_pred_rads + yaw_rate_meas_rads")
    p.add_argument("--baseline-rmse", type=float, default=None,
                   help="V0 baseline RMSE to compare against. If omitted, falls back to "
                        "RMSE of yaw_rate_resid_rads column if present.")
    args = p.parse_args()

    df = pd.read_csv(args.csv)
    for col in ("yaw_rate_pred_rads", "yaw_rate_meas_rads"):
        if col not in df.columns:
            print(f"SENSOR FAIL: missing column {col!r}", file=sys.stderr)
            return 1

    pred = df["yaw_rate_pred_rads"].to_numpy()
    meas = df["yaw_rate_meas_rads"].to_numpy()
    if "delta_road_rad" in df.columns:
        mask = np.abs(df["delta_road_rad"].to_numpy()) >= REGIME_DELTA_THR
    else:
        mask = np.ones(len(df), dtype=bool)
    sub_pred = pred[mask]
    sub_meas = meas[mask]

    ok = True
    if sub_pred.size >= 2 and np.std(sub_pred) > 0 and np.std(sub_meas) > 0:
        corr = float(np.corrcoef(sub_pred, sub_meas)[0, 1])
    else:
        corr = float("nan")
    if not (corr > 0):
        print(f"SENSOR FAIL: sign-consistency check — corr(pred, meas) on cornering = {corr:.3f} (need > 0)")
        ok = False
    else:
        print(f"sensor PASS sign-consistency: corr(pred, meas) on cornering = {corr:.3f}")

    rmse_cand = rmse(pred - meas)
    if args.baseline_rmse is not None:
        baseline = args.baseline_rmse
    elif "yaw_rate_resid_rads" in df.columns:
        baseline = rmse(df["yaw_rate_resid_rads"].to_numpy())
    else:
        baseline = float("inf")
    if not (rmse_cand <= baseline + 1e-9):
        print(f"SENSOR FAIL: regression check — RMSE(candidate) = {rmse_cand:.5f} > V0 = {baseline:.5f}")
        ok = False
    else:
        print(f"sensor PASS regression-check: RMSE(candidate) = {rmse_cand:.5f} ≤ V0 = {baseline:.5f}")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
