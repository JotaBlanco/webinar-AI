"""Baseline residual computation on existing Ford sim CSVs.

Reads existing data/sim/segments/<PLATFORM>/.../sim.csv files (read-only),
computes RMSE, correlation, and regime-stratified residuals,
and writes a summary CSV + a text table to modulo-1/out/.
"""
from __future__ import annotations

import glob
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd

DATA_SIM = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/data/sim/segments")
OUT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/modulo-1/out")
OUT.mkdir(parents=True, exist_ok=True)

PLATFORMS = ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"]


def load_platform(platform: str) -> pd.DataFrame:
    files = sorted(glob.glob(str(DATA_SIM / platform / "**" / "sim.csv"), recursive=True))
    frames = []
    for f in files:
        df = pd.read_csv(f)
        df["segment"] = f
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def metrics(df: pd.DataFrame, label: str) -> dict:
    # Drop NaN/Inf in either prediction or measurement
    sub = df.dropna(subset=["yaw_rate_meas_rads", "yaw_rate_pred_rads",
                            "a_lat_meas_mps2", "a_y_pred_mps2"]).copy()
    yr_meas = sub["yaw_rate_meas_rads"].to_numpy()
    yr_pred = sub["yaw_rate_pred_rads"].to_numpy()
    ay_meas = sub["a_lat_meas_mps2"].to_numpy()
    ay_pred = sub["a_y_pred_mps2"].to_numpy()

    rmse_yr_rads = float(np.sqrt(np.mean((yr_meas - yr_pred) ** 2)))
    rmse_yr_degs = math.degrees(rmse_yr_rads)
    rmse_ay = float(np.sqrt(np.mean((ay_meas - ay_pred) ** 2)))
    bias_yr_rads = float(np.mean(yr_meas - yr_pred))
    bias_yr_degs = math.degrees(bias_yr_rads)
    bias_ay = float(np.mean(ay_meas - ay_pred))
    corr_yr = float(np.corrcoef(yr_meas, yr_pred)[0, 1])
    corr_ay = float(np.corrcoef(ay_meas, ay_pred)[0, 1])

    return {
        "label": label,
        "n": len(sub),
        "rmse_yaw_rate_degs": rmse_yr_degs,
        "rmse_a_y_mps2": rmse_ay,
        "bias_yaw_rate_degs": bias_yr_degs,
        "bias_a_y_mps2": bias_ay,
        "corr_yaw_rate": corr_yr,
        "corr_a_y": corr_ay,
    }


def regime_breakdown(df: pd.DataFrame, label: str) -> pd.DataFrame:
    sub = df.dropna(subset=["yaw_rate_meas_rads", "yaw_rate_pred_rads"]).copy()
    sub["resid_yr_degs"] = np.degrees(sub["yaw_rate_meas_rads"] - sub["yaw_rate_pred_rads"])
    sub["abs_delta_deg"] = sub["delta_wheel_deg"].abs()
    sub["abs_a_y"] = sub["a_lat_meas_mps2"].abs()

    bins = {
        "v_mps": [0, 5, 15, 25, 40],
        "abs_delta_deg": [0, 5, 30, 90, 540],
        "abs_a_y": [0, 0.5, 2.0, 5.0, 15.0],
    }
    rows = []
    for col, edges in bins.items():
        cats = pd.cut(sub[col], edges, include_lowest=True)
        grp = sub.groupby(cats, observed=True)["resid_yr_degs"]
        for k, g in grp:
            if len(g) == 0:
                continue
            rows.append({
                "platform": label,
                "regime_col": col,
                "bin": str(k),
                "n": len(g),
                "rmse_yr_degs": float(np.sqrt(np.mean(g ** 2))),
                "bias_yr_degs": float(g.mean()),
            })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    summary_rows = []
    regime_frames = []
    for plat in PLATFORMS:
        df = load_platform(plat)
        print(f"{plat}: {len(df)} rows, {df['segment'].nunique()} segments")
        m = metrics(df, plat)
        summary_rows.append(m)
        regime_frames.append(regime_breakdown(df, plat))

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(OUT / "baseline_summary.csv", index=False)
    print("\nBaseline summary:")
    print(summary.to_string(index=False))

    regimes = pd.concat(regime_frames, ignore_index=True)
    regimes.to_csv(OUT / "baseline_regimes.csv", index=False)
    print("\nWorst regimes (top 10 by rmse_yr_degs):")
    print(regimes.sort_values("rmse_yr_degs", ascending=False).head(10).to_string(index=False))
