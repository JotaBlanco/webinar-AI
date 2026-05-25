"""Diagnose the residual structure for both Ford platforms.

For KS speed-known: psi_dot_pred = (v / L) * tan(delta_road).
If the residual is dominated by a scale factor k, then psi_dot_meas ~ k * psi_dot_pred,
which can be absorbed as an effective steering-ratio or wheelbase correction.

We also check whether a steering lag (compliance) better explains it.
"""
from __future__ import annotations
import glob
from pathlib import Path
import numpy as np
import pandas as pd

DATA_SIM = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/data/sim/segments")
OUT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/modulo-1/out")

PLATFORMS = ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"]


def load(platform):
    files = sorted(glob.glob(str(DATA_SIM / platform / "**" / "sim.csv"), recursive=True))
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)


def fit_scale(meas, pred):
    """Least-squares slope k such that meas ~ k * pred (no intercept)."""
    num = float(np.sum(meas * pred))
    den = float(np.sum(pred * pred))
    return num / den if den > 0 else float("nan")


def fit_affine(meas, pred):
    """meas ~ k*pred + b."""
    a, b = np.polyfit(pred, meas, 1)
    return float(a), float(b)


def best_lag(meas, pred, max_lag=25):
    """Find lag (in samples) that maximizes pearson correlation between meas and pred shifted forward."""
    best = (0, -1.0)
    for L in range(-max_lag, max_lag + 1):
        if L >= 0:
            m = meas[L:]
            p = pred[: len(p_arr := pred)][: len(meas) - L]
            p = pred[: len(meas) - L]
        else:
            m = meas[: len(meas) + L]
            p = pred[-L:]
        if len(m) < 10:
            continue
        c = float(np.corrcoef(m, p)[0, 1])
        if c > best[1]:
            best = (L, c)
    return best


for plat in PLATFORMS:
    df = load(plat).dropna(subset=["yaw_rate_meas_rads", "yaw_rate_pred_rads"])
    yr_m = df["yaw_rate_meas_rads"].to_numpy()
    yr_p = df["yaw_rate_pred_rads"].to_numpy()

    k = fit_scale(yr_m, yr_p)
    a, b = fit_affine(yr_m, yr_p)

    # If we apply the scale, what's the RMSE?
    rmse_orig = float(np.sqrt(np.mean((yr_m - yr_p) ** 2)))
    rmse_scaled = float(np.sqrt(np.mean((yr_m - k * yr_p) ** 2)))
    rmse_affine = float(np.sqrt(np.mean((yr_m - (a * yr_p + b)) ** 2)))

    lag, corr = best_lag(yr_m, yr_p, max_lag=25)

    print(f"\n=== {plat} ===")
    print(f"  N                = {len(df)}")
    print(f"  RMSE (raw)       = {np.degrees(rmse_orig):.4f} deg/s")
    print(f"  best scalar k    = {k:.4f}  -> RMSE k*pred = {np.degrees(rmse_scaled):.4f} deg/s")
    print(f"  affine (a, b)    = ({a:.4f}, {b:.5f} rad/s)   -> RMSE = {np.degrees(rmse_affine):.4f} deg/s")
    print(f"  best lag samples = {lag} (corr={corr:.3f})  [+L = pred leads meas]")

    # Compare to mean of meas/pred over significant turns
    mask = np.abs(yr_p) > np.radians(2.0)  # >2 deg/s
    if mask.sum() > 50:
        ratio = float(np.mean(yr_m[mask] / yr_p[mask]))
        print(f"  mean(meas/pred) on |pred|>2deg/s ({mask.sum()} pts): {ratio:.3f}")
