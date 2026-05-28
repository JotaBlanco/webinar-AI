#!/usr/bin/env python3
"""run_ladder.py — disciplined variant ladder for lateral-fidelity challenge.

V0: yaw_rate_resid_rads as-is (no preprocessing).
V1: per-platform bias removal — subtract median residual fitted on TRAIN, applied to TEST.
V2: lag alignment — best integer-sample shift of pred vs meas, fitted on TRAIN.
V3: steering gain calibration — single per-platform scalar k so pred_yaw_rate := k * pred_yaw_rate. Fit on TRAIN (cornering only).
V4: linear speed-residual correction — fit residual ≈ a + b * v on TRAIN, subtract from pred.

Interleaved split: every 5th sample → test. RMSE reported on TEST.
Regime mask identical to baseline-residual.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

REGIME_DELTA_THR = 0.01
REGIME_DDELTA_THR = 0.05

def regime_mask(df):
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

def rmse(a):
    s = np.asarray(a, dtype=float); s = s[np.isfinite(s)]
    return float(np.sqrt(np.mean(s ** 2))) if s.size else float("nan")

def per_regime(resid, mask):
    out = {"overall": rmse(resid)}
    for r in ("straight", "steady", "transient"):
        m = (mask == r).to_numpy()
        out[r] = rmse(resid[m])
    return out

def best_shift(pred, meas, max_shift=10):
    """Find integer shift s minimizing RMSE(pred shifted by s vs meas).
    Positive s: pred is delayed (use pred[s:] vs meas[:-s])."""
    best_s, best_e = 0, rmse(pred - meas)
    for s in range(-max_shift, max_shift + 1):
        if s == 0: continue
        if s > 0:
            p, m = pred[s:], meas[:-s]
        else:
            p, m = pred[:s], meas[-s:]
        e = rmse(p - m)
        if e < best_e:
            best_e, best_s = e, s
    return best_s

def shift_array(arr, s):
    """Shift array by s samples, padding edges with edge value."""
    out = np.empty_like(arr)
    if s == 0:
        out[:] = arr
    elif s > 0:
        out[:s] = arr[0]
        out[s:] = arr[:-s]
    else:
        out[s:] = arr[-1]
        out[:s] = arr[-s:]
    return out

def main():
    if len(sys.argv) != 2:
        print("usage: run_ladder.py <PLATFORM>", file=sys.stderr); sys.exit(2)
    platform = sys.argv[1]
    data_root = Path("data/sim/segments") / platform
    csvs = sorted(data_root.rglob("sim.csv"))
    frames = [pd.read_csv(p) for p in csvs]
    big = pd.concat(frames, ignore_index=True)
    n = len(big)
    mask = regime_mask(big)

    # Interleaved split
    idx = np.arange(n)
    test = idx[4::5]
    train = np.setdiff1d(idx, test)
    test_mask = mask.iloc[test].reset_index(drop=True)

    # raw arrays
    pred0 = big["yaw_rate_pred_rads"].to_numpy().copy()
    meas  = big["yaw_rate_meas_rads"].to_numpy().copy()
    delta = big["delta_road_rad"].to_numpy().copy()
    v     = big["v_mps"].to_numpy().copy()

    # V0 — as-is, scored on TEST
    resid0_test = pred0[test] - meas[test]
    r0 = per_regime(resid0_test, test_mask)

    rows = [("V0 baseline (as-is)", r0, None, "per-platform")]
    prev = r0["overall"]

    # V1 — bias removal: fit median resid on TRAIN
    bias = float(np.median(pred0[train] - meas[train]))
    pred1 = pred0 - bias
    r1_test = pred1[test] - meas[test]
    r1 = per_regime(r1_test, test_mask)
    rows.append((f"V1 bias removal (b={bias:+.5f})", r1, prev - r1["overall"], "per-platform"))
    prev = r1["overall"]

    # V2 — lag alignment: find best integer shift on TRAIN
    s = best_shift(pred1[train], meas[train], max_shift=10)
    pred2 = shift_array(pred1, s)
    r2_test = pred2[test] - meas[test]
    r2 = per_regime(r2_test, test_mask)
    rows.append((f"V2 lag alignment (shift={s} samples = {s*0.02:+.3f}s)", r2, prev - r2["overall"], "per-platform"))
    prev = r2["overall"]

    # V3 — steering-gain k: scale pred by k. Fit on TRAIN cornering only.
    train_mask = mask.iloc[train].reset_index(drop=True)
    corn = (train_mask != "straight").to_numpy()
    pt = pred2[train][corn]; mt = meas[train][corn]
    # min over k of ||k*pt - mt||^2 => k = (pt.mt)/(pt.pt)
    k = float(np.dot(pt, mt) / np.dot(pt, pt))
    pred3 = k * pred2
    r3_test = pred3[test] - meas[test]
    r3 = per_regime(r3_test, test_mask)
    rows.append((f"V3 steering gain (k={k:.4f})", r3, prev - r3["overall"], "per-platform"))
    prev = r3["overall"]

    # V4 — speed-residual correction: residual ≈ a + b*v, fit on TRAIN
    res_train = pred3[train] - meas[train]
    vt = v[train]
    A = np.column_stack([np.ones_like(vt), vt])
    coef, *_ = np.linalg.lstsq(A, res_train, rcond=None)
    a, b = float(coef[0]), float(coef[1])
    pred4 = pred3 - (a + b * v)
    r4_test = pred4[test] - meas[test]
    r4 = per_regime(r4_test, test_mask)
    rows.append((f"V4 speed-residual (a={a:+.5f}, b={b:+.6f}/mps)", r4, prev - r4["overall"], "per-platform"))
    prev = r4["overall"]

    # Print table
    print(f"Platform: {platform}")
    print(f"Total samples: {n}  train: {len(train)}  test: {len(test)}")
    print(f"{'Variant':<55s} {'overall':>10s} {'straight':>10s} {'steady':>10s} {'transient':>10s} {'marginal':>10s} {'scope':>14s}")
    for name, r, marg, scope in rows:
        margs = f"{marg:+.5f}" if marg is not None else "    —    "
        flag = " REGRESSION" if (marg is not None and marg < 0) else ""
        print(f"{name:<55s} {r['overall']:>10.5f} {r['straight']:>10.5f} {r['steady']:>10.5f} {r['transient']:>10.5f} {margs:>10s} {scope:>14s}{flag}")

    total = r0["overall"] - rows[-1][1]["overall"]
    marg_sum = sum(r[2] for r in rows[1:] if r[2] is not None)
    err = abs(marg_sum - total) / abs(total) if total else float("inf")
    print(f"\nAttribution coherence: |Σmarg − total|/|total| = {err:.4f}  (must be < 0.15)")
    print(f"V0 overall: {r0['overall']:.5f}    V4 overall: {rows[-1][1]['overall']:.5f}    total drop: {total:+.5f} ({100*total/r0['overall']:+.1f}%)")

if __name__ == "__main__":
    main()
