"""Extends ladder.py with two more variants:
  v5: time-shift the steering input to align with measured yaw rate
       (single global lag from cross-correlation)
  v6: per-segment static steering offset (fit each segment independently)

Built on top of v4's understeer-K refit.
"""
from __future__ import annotations

import glob
import os
import sys

import numpy as np
import pandas as pd

DATA_ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-05/data/sim/segments"

L_BY_PLAT = {
    "FORD_MUSTANG_MACH_E_MK1":  2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.700,
}


def load_segments():
    paths = []
    for plat in L_BY_PLAT:
        paths.extend(glob.glob(os.path.join(DATA_ROOT, plat, "**", "sim.csv"),
                               recursive=True))
    out = []
    for p in sorted(paths):
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        for plat in L_BY_PLAT:
            if plat in p:
                out.append((plat, p, df))
                break
    return out


def rmse(a, b):
    return float(np.sqrt(np.mean((a - b) ** 2)))


def fit_lag_one_segment(df, plat, max_lag=15):
    """Find the integer sample lag (50 Hz; +ve = yaw measured lags steering)
    that maximises correlation between (v/L)*tan(δ) shifted forward
    and yaw_meas. We restrict to lags in [-max_lag, +max_lag]."""
    L = L_BY_PLAT[plat]
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    yaw_pred0 = (v / L) * np.tan(delta)
    yaw_meas = df["yaw_rate_meas_rads"].to_numpy()
    n = len(yaw_meas)
    m = (np.abs(df["a_lat_meas_mps2"].to_numpy()) < 15) & (v > 5)
    if m.sum() < 200:
        return 0
    best_lag, best_score = 0, -np.inf
    for lag in range(-max_lag, max_lag + 1):
        if lag >= 0:
            a = yaw_pred0[:n - lag]
            b = yaw_meas[lag:]
            mm = m[:n - lag] & m[lag:]
        else:
            k = -lag
            a = yaw_pred0[k:]
            b = yaw_meas[:n - k]
            mm = m[k:] & m[:n - k]
        if mm.sum() < 200:
            continue
        # use negative MSE as score, restricted to mm
        d = (a[mm] - b[mm])
        score = -float(np.mean(d * d))
        if score > best_score:
            best_score = score
            best_lag = lag
    return best_lag


def fit_per_segment_offset(df, plat, K):
    """Linear LS for delta_off given understeer K:
        yaw_meas * (L + K v²) = v*(δ + off)
    """
    L = L_BY_PLAT[plat]
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    yaw = df["yaw_rate_meas_rads"].to_numpy()
    m = (np.abs(df["a_lat_meas_mps2"].to_numpy()) < 15) & (v > 5)
    if m.sum() < 100:
        return 0.0
    # yaw*(L+Kv²) - v*δ = v*off  →  off = sum(v*(...)) / sum(v²)
    rhs = yaw[m] * (L + K * v[m] ** 2) - v[m] * delta[m]
    num = float(np.sum(v[m] * rhs))
    den = float(np.sum(v[m] ** 2)) + 1e-12
    return num / den


def main():
    segments = load_segments()
    print(f"Loaded {len(segments)} Ford segments.")

    # Refit understeer K per platform (same as ladder.py v4)
    K_fit = {}
    for plat in L_BY_PLAT:
        L = L_BY_PLAT[plat]
        num = den = 0.0
        for p, _, df in segments:
            if p != plat:
                continue
            v = df["v_mps"].to_numpy()
            delta = df["delta_road_rad"].to_numpy()
            yaw = df["yaw_rate_meas_rads"].to_numpy()
            m = (np.abs(df["a_lat_meas_mps2"].to_numpy()) < 15) & (v > 5)
            x = (yaw * v * v)[m]
            y = (v * delta - L * yaw)[m]
            w = v[m] - 4.0
            num += float(np.sum(w * x * y))
            den += float(np.sum(w * x * x))
        K_fit[plat] = num / (den + 1e-12)
    print(f"K_fit = {K_fit}")

    # Fit per-platform global steering offset given K
    off_glob = {}
    for plat in L_BY_PLAT:
        L = L_BY_PLAT[plat]
        K = K_fit[plat]
        num = den = 0.0
        for p, _, df in segments:
            if p != plat:
                continue
            v = df["v_mps"].to_numpy()
            delta = df["delta_road_rad"].to_numpy()
            yaw = df["yaw_rate_meas_rads"].to_numpy()
            m = (np.abs(df["a_lat_meas_mps2"].to_numpy()) < 15) & (v > 5)
            rhs = yaw[m] * (L + K * v[m] ** 2) - v[m] * delta[m]
            num += float(np.sum(v[m] * rhs))
            den += float(np.sum(v[m] ** 2))
        off_glob[plat] = num / (den + 1e-12)
    print(f"global offsets = {off_glob}")

    def predict(df, plat, *, off=0.0, K=None, shift=0):
        L = L_BY_PLAT[plat]
        if K is None:
            K = K_fit[plat]
        v = df["v_mps"].to_numpy()
        delta = df["delta_road_rad"].to_numpy() + off
        pred = v * delta / (L + K * v ** 2)
        if shift != 0:
            n = len(pred)
            if shift > 0:
                # yaw lags steering by 'shift' samples → shift pred forward
                pred_out = np.empty_like(pred)
                pred_out[shift:] = pred[:n - shift]
                pred_out[:shift] = pred[0]
                return pred_out
            else:
                k = -shift
                pred_out = np.empty_like(pred)
                pred_out[:n - k] = pred[k:]
                pred_out[n - k:] = pred[-1]
                return pred_out
        return pred

    def score(predict_with_args):
        pred_all = []
        meas_all = []
        for plat, _, df in segments:
            pred = predict_with_args(df, plat)
            meas = df["yaw_rate_meas_rads"].to_numpy()
            m = np.abs(df["a_lat_meas_mps2"].to_numpy()) < 15
            pred_all.append(pred[m])
            meas_all.append(meas[m])
        p = np.concatenate(pred_all)
        m = np.concatenate(meas_all)
        return rmse(p, m), len(p)

    # Baseline (v4 from ladder.py)
    r_v4, _ = score(lambda df, plat: predict(df, plat,
                                              off=off_glob[plat]))
    print(f"\n[v4 recompute] global-offset + K-refit: RMSE = {r_v4:.5f}")

    # v5: single global lag per platform from pooled cross-correlation
    print("\nFitting global lag per platform...")
    global_lag = {}
    for plat in L_BY_PLAT:
        # accumulate sample lag votes weighted by segment length
        lags = []
        for p, _, df in segments:
            if p != plat:
                continue
            if len(df) < 500:
                continue
            lag = fit_lag_one_segment(df, plat, max_lag=10)
            lags.append(lag)
        median_lag = int(np.median(lags)) if lags else 0
        global_lag[plat] = median_lag
        print(f"  {plat}: median lag = {median_lag} samples "
              f"({median_lag * 20:.0f} ms at 50Hz; n_segs={len(lags)})")

    r_v5, _ = score(lambda df, plat: predict(df, plat,
                                              off=off_glob[plat],
                                              shift=global_lag[plat]))
    print(f"\n[v5] + global per-platform time-shift: RMSE = {r_v5:.5f}")

    # v6: per-segment offset (overrides global offset)
    print("\nFitting per-segment offsets...")
    seg_off = {}
    for plat, path, df in segments:
        seg_off[path] = fit_per_segment_offset(df, plat, K_fit[plat])
    offs_arr = np.array([seg_off[p] for _, p, _ in segments])
    print(f"  per-segment offset: mean={offs_arr.mean():+.5f} "
          f"std={offs_arr.std():.5f}  "
          f"p5/p95 = {np.percentile(offs_arr,5):+.5f}/{np.percentile(offs_arr,95):+.5f}")

    def predict_segoff(df, plat):
        return predict(df, plat, off=seg_off.get_path_off(df))

    # We can't grab path inside predict — wrap differently
    pred_all = []
    meas_all = []
    for plat, path, df in segments:
        off = seg_off[path]
        pred = predict(df, plat, off=off, shift=global_lag[plat])
        meas = df["yaw_rate_meas_rads"].to_numpy()
        m = np.abs(df["a_lat_meas_mps2"].to_numpy()) < 15
        pred_all.append(pred[m])
        meas_all.append(meas[m])
    pcat = np.concatenate(pred_all)
    mcat = np.concatenate(meas_all)
    r_v6 = rmse(pcat, mcat)
    print(f"\n[v6] + per-segment steering offset (on top of v5): RMSE = {r_v6:.5f}")

    # And without lag (per-seg offset only on top of v4)
    pred_all = []
    meas_all = []
    for plat, path, df in segments:
        off = seg_off[path]
        pred = predict(df, plat, off=off, shift=0)
        meas = df["yaw_rate_meas_rads"].to_numpy()
        m = np.abs(df["a_lat_meas_mps2"].to_numpy()) < 15
        pred_all.append(pred[m])
        meas_all.append(meas[m])
    pcat = np.concatenate(pred_all)
    mcat = np.concatenate(meas_all)
    r_v6b = rmse(pcat, mcat)
    print(f"[v6b] per-segment offset alone (no lag): RMSE = {r_v6b:.5f}")

    # Final summary
    print("\n" + "=" * 64)
    print("FULL LADDER (sequential)")
    print("=" * 64)
    # Re-use ladder1 numbers
    rows = [
        ("v0 baseline (unfiltered, KS prediction column)", 0.01804),
        ("v1 + outlier mask (|a_lat|<15)",                 0.01804),
        ("v2 + global steering offset",                    0.01792),
        ("v3 + canonical understeer (Caf/Car prior)",      0.01628),
        ("v4 + understeer-K refit",                        r_v4),
        ("v5 + global time-shift (sample lag)",            r_v5),
        ("v6 + per-segment offset",                        r_v6),
    ]
    prev = rows[0][1]
    base = rows[0][1]
    for name, r in rows:
        d = prev - r
        pct = 100 * d / base
        print(f"  {name:48s}  RMSE={r:.5f}  Δ={d:+.5f}  ({pct:+5.2f}%)")
        prev = r
    final = rows[-1][1]
    print(f"\n  Total: {base:.5f} → {final:.5f} "
          f"({100*(base-final)/base:+.2f}% improvement)")


if __name__ == "__main__":
    main()
