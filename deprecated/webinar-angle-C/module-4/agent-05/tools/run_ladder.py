#!/usr/bin/env python3
"""Run the locked V0->V4 variant ladder per the plan.

Outputs:
  out/variant_table_<PLATFORM>.csv  - rows = variants, cols = overall + per-regime
  out/variant_summary.txt           - human-readable summary

Usage:
  python3 tools/run_ladder.py FORD_MUSTANG_MACH_E_MK1
  python3 tools/run_ladder.py FORD_F_150_LIGHTNING_MK1
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

REGIME_DELTA_THR = 0.01
REGIME_DDELTA_THR = 0.05
LAG_MAX = 10  # samples at 50 Hz = 200 ms


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


def rmse_breakdown(resid: np.ndarray, regime: np.ndarray, test_mask: np.ndarray) -> dict:
    out = {"overall": rmse(resid[test_mask])}
    for r in ("straight", "steady", "transient"):
        m = test_mask & (regime == r)
        out[r] = rmse(resid[m])
    return out


def load_platform(platform: str) -> pd.DataFrame:
    data_root = Path("data/sim/segments") / platform
    csvs = sorted(data_root.rglob("sim.csv"))
    frames = []
    for p in csvs:
        df = pd.read_csv(p)
        df["__segment__"] = str(p.parent)
        frames.append(df)
    big = pd.concat(frames, ignore_index=True)
    return big


def shift_within_segments(arr: np.ndarray, segments: np.ndarray, n: int) -> np.ndarray:
    """Shift arr by n samples within each segment (positive n => arr[t-n])."""
    if n == 0:
        return arr.copy()
    out = np.empty_like(arr, dtype=float)
    out[:] = np.nan
    # process per segment
    uniq, idx = np.unique(segments, return_inverse=True)
    order = np.argsort(idx, kind="stable")
    sorted_idx = idx[order]
    sorted_arr = arr[order]
    # find segment boundaries
    boundaries = np.concatenate(([0], np.where(np.diff(sorted_idx) != 0)[0] + 1, [len(sorted_arr)]))
    shifted = np.empty_like(sorted_arr, dtype=float)
    shifted[:] = np.nan
    for i in range(len(boundaries) - 1):
        s, e = boundaries[i], boundaries[i+1]
        seg = sorted_arr[s:e]
        if n < len(seg):
            shifted[s+n:e] = seg[:len(seg)-n]
    # invert order
    inv = np.empty_like(order)
    inv[order] = np.arange(len(order))
    out = shifted[inv]
    return out


def main():
    if len(sys.argv) != 2:
        print("usage: run_ladder.py <PLATFORM>", file=sys.stderr); sys.exit(2)
    platform = sys.argv[1]
    print(f"\n=== Variant ladder for {platform} ===")

    df = load_platform(platform)
    n = len(df)
    print(f"Loaded {df['__segment__'].nunique()} segments, {n} samples")

    # Interleaved split: every 5th sample -> test
    test_mask = (np.arange(n) % 5 == 0)
    train_mask = ~test_mask

    pred0 = df["yaw_rate_pred_rads"].to_numpy().astype(float)
    meas = df["yaw_rate_meas_rads"].to_numpy().astype(float)
    delta = df["delta_road_rad"].to_numpy().astype(float)
    segments = df["__segment__"].to_numpy()
    regime = regime_mask(df).to_numpy()

    cornering = np.abs(delta) >= REGIME_DELTA_THR

    results = []

    # V0 - as-is residual
    resid = pred0 - meas
    r = rmse_breakdown(resid, regime, test_mask)
    r["variant"] = "V0_baseline"; r["fit"] = "-"; r["params"] = ""
    results.append(r)

    # V1 - per-platform bias
    b = float(np.mean(pred0[train_mask] - meas[train_mask]))
    pred1 = pred0 - b
    resid1 = pred1 - meas
    r = rmse_breakdown(resid1, regime, test_mask)
    r["variant"] = "V1_bias"; r["fit"] = "per-platform"; r["params"] = f"b={b:.5f}"
    results.append(r)

    # V2 - per-platform steering gain on (pred1) using cornering samples
    train_corner = train_mask & cornering
    num = float(np.sum(pred1[train_corner] * meas[train_corner]))
    den = float(np.sum(pred1[train_corner] * pred1[train_corner]))
    k = num / den if den > 0 else 1.0
    pred2 = k * pred1
    resid2 = pred2 - meas
    r = rmse_breakdown(resid2, regime, test_mask)
    r["variant"] = "V2_gain"; r["fit"] = "per-platform"; r["params"] = f"k={k:.4f}"
    results.append(r)

    # V3 - per-platform integer lag on pred2 (real vehicle yaw lags steering)
    # We shift the prediction forward (delay it) by n samples within each segment
    best_n, best_rmse = 0, float("inf")
    for cand in range(LAG_MAX + 1):
        shifted = shift_within_segments(pred2, segments, cand)
        diff = shifted - meas
        valid = train_mask & np.isfinite(diff)
        score = rmse(diff[valid])
        if score < best_rmse:
            best_rmse = score; best_n = cand
    pred3 = shift_within_segments(pred2, segments, best_n)
    resid3 = pred3 - meas
    # for test rmse, drop NaNs (head of each segment)
    finite = np.isfinite(resid3)
    r = rmse_breakdown(np.where(finite, resid3, 0.0), regime, test_mask & finite)
    r["variant"] = "V3_lag"; r["fit"] = "per-platform"; r["params"] = f"n={best_n} samples ({best_n*20} ms)"
    results.append(r)

    # V4 - per-segment additive bias on top (calibration label)
    pred4 = pred3.copy()
    for seg in np.unique(segments):
        m = (segments == seg) & train_mask & np.isfinite(pred3)
        if m.sum() > 10:
            seg_bias = float(np.mean(pred3[m] - meas[m]))
            pred4[segments == seg] = pred3[segments == seg] - seg_bias
    resid4 = pred4 - meas
    finite4 = np.isfinite(resid4)
    r = rmse_breakdown(np.where(finite4, resid4, 0.0), regime, test_mask & finite4)
    r["variant"] = "V4_per_seg_bias"; r["fit"] = "per-SEGMENT (calibration)"; r["params"] = "N segment biases"
    results.append(r)

    # Build table
    table = pd.DataFrame(results)[["variant", "fit", "params", "overall", "straight", "steady", "transient"]]
    table["marginal_overall"] = -table["overall"].diff()  # positive = improvement
    print("\n" + table.to_string(index=False, float_format=lambda x: f"{x:.5f}"))

    # Attribution coherence
    total_drop = float(table["overall"].iloc[0] - table["overall"].iloc[-1])
    sum_marg = float(table["marginal_overall"].iloc[1:].sum())
    coh = abs(sum_marg - total_drop) / abs(total_drop) if total_drop != 0 else float("nan")
    print(f"\nTotal drop V0->V4: {total_drop:.5f} rad/s")
    print(f"Sum of marginals:  {sum_marg:.5f} rad/s")
    print(f"Attribution coherence: {coh:.4f}  (target < 0.15)")

    # Regression flags
    print("\nRegressions:")
    any_reg = False
    for _, row in table.iloc[1:].iterrows():
        if row["marginal_overall"] is not None and row["marginal_overall"] < 0:
            print(f"  [REGRESSION] {row['variant']}: Δ={row['marginal_overall']:+.5f}")
            any_reg = True
    if not any_reg:
        print("  none")

    out_dir = Path("out")
    out_dir.mkdir(exist_ok=True)
    table.to_csv(out_dir / f"variant_table_{platform}.csv", index=False)
    print(f"\nWrote out/variant_table_{platform}.csv")


if __name__ == "__main__":
    main()
