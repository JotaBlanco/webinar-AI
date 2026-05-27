"""Compute baseline lateral-prediction error across all Ford sim CSVs.

Headline metric: RMSE of yaw-rate residual across all samples in all Ford
segments (Mach-E + F-150). Also report MAE, R^2, and per-platform breakdown.
"""
from __future__ import annotations

import csv
import glob
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-08")
SIM_BASE = ROOT / "data" / "sim" / "segments"
PLATFORMS = ("FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1")


def load_all(platform: str) -> pd.DataFrame:
    paths = sorted(SIM_BASE.joinpath(platform).rglob("sim.csv"))
    frames = []
    for p in paths:
        try:
            df = pd.read_csv(p, usecols=[
                "t_s", "delta_road_rad", "v_mps",
                "yaw_rate_meas_rads", "a_lat_meas_mps2",
                "yaw_rate_pred_rads", "a_y_pred_mps2",
            ])
        except Exception as e:
            continue
        df["__seg"] = str(p.relative_to(SIM_BASE))
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def rmse(x):
    return float(np.sqrt(np.mean(x ** 2)))


def metrics(meas, pred, label=""):
    r = meas - pred
    out = {
        "label": label,
        "n": len(meas),
        "rmse": rmse(r),
        "mae": float(np.mean(np.abs(r))),
        "bias": float(np.mean(r)),
        "rmse_deg_s": float(np.degrees(rmse(r))) if "yaw" in label else None,
    }
    # R^2 vs measured variance
    if np.var(meas) > 0:
        out["r2"] = 1.0 - np.var(r) / np.var(meas)
    return out


def main():
    print("Loading sim CSVs...")
    dfs = {}
    for plat in PLATFORMS:
        df = load_all(plat)
        dfs[plat] = df
        print(f"  {plat}: {len(df)} samples across "
              f"{df['__seg'].nunique()} segments")
    full = pd.concat([dfs[p] for p in PLATFORMS], ignore_index=True)
    print(f"  TOTAL: {len(full)} samples")

    print("\n=== BASELINE METRICS (raw KS prediction vs measured) ===")
    print("\nYaw rate (rad/s):")
    for plat in PLATFORMS:
        df = dfs[plat]
        m = metrics(df["yaw_rate_meas_rads"].values,
                    df["yaw_rate_pred_rads"].values, "yaw_rate")
        print(f"  {plat}: RMSE={m['rmse']:.5f} rad/s  "
              f"= {np.degrees(m['rmse']):.3f} deg/s  "
              f"bias={np.degrees(m['bias']):.3f} deg/s  "
              f"R2={m['r2']:.4f}")
    m = metrics(full["yaw_rate_meas_rads"].values,
                full["yaw_rate_pred_rads"].values, "yaw_rate")
    print(f"  COMBINED: RMSE={m['rmse']:.5f} rad/s "
          f"= {np.degrees(m['rmse']):.3f} deg/s  "
          f"bias={np.degrees(m['bias']):.4f} deg/s  R2={m['r2']:.4f}")

    print("\nLateral accel a_y (m/s^2):")
    for plat in PLATFORMS:
        df = dfs[plat]
        m = metrics(df["a_lat_meas_mps2"].values,
                    df["a_y_pred_mps2"].values, "a_y")
        print(f"  {plat}: RMSE={m['rmse']:.4f} m/s²  "
              f"bias={m['bias']:.4f}  R2={m['r2']:.4f}")
    m = metrics(full["a_lat_meas_mps2"].values,
                full["a_y_pred_mps2"].values, "a_y")
    print(f"  COMBINED: RMSE={m['rmse']:.4f} m/s²  "
          f"bias={m['bias']:.4f}  R2={m['r2']:.4f}")

    # Save concatenated data for reuse
    out = ROOT / "out" / "all_ford.parquet"
    out.parent.mkdir(exist_ok=True)
    full.to_parquet(out)
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
