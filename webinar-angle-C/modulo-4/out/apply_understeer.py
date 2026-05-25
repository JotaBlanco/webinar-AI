"""Understeer-gradient correction on yaw_rate_pred.

For each platform, fits a single scalar `k` such that
    psi_dot_pred_corrected = psi_dot_pred_baseline * (1 - k * |a_y_pred|)
minimises pooled RMSE of `yaw_rate_meas - psi_dot_pred_corrected` across that
platform's segments. Then writes the corrected CSVs to <out-dir>, mirroring the
input directory layout, and re-derives the residual columns.

Usage:
    python out/apply_understeer.py <input-sim-dir> <output-dir>
"""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar


def rmse(x):
    return float(np.sqrt(np.mean(np.square(x))))


def fit_k(meas, pred_yaw, pred_ay):
    # Loss as a function of k
    def loss(k):
        corrected = pred_yaw * (1.0 - k * np.abs(pred_ay))
        return rmse(meas - corrected)
    res = minimize_scalar(loss, bounds=(-1.0, 1.0), method="bounded")
    return float(res.x), float(res.fun)


def main():
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    in_dir = Path(sys.argv[1])
    out_dir = Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    for plat_dir in sorted(in_dir.iterdir()):
        if not plat_dir.is_dir() or not plat_dir.name.startswith("FORD_"):
            continue
        csvs = sorted(plat_dir.rglob("*.csv"))
        if not csvs:
            continue
        meas_all, pred_yaw_all, pred_ay_all = [], [], []
        for c in csvs:
            df = pd.read_csv(c)
            meas_all.append(df["yaw_rate_meas_rads"].values)
            pred_yaw_all.append(df["yaw_rate_pred_rads"].values)
            pred_ay_all.append(df["a_y_pred_mps2"].values)
        meas = np.concatenate(meas_all)
        pred_yaw = np.concatenate(pred_yaw_all)
        pred_ay = np.concatenate(pred_ay_all)
        k, fit_rmse_rad = fit_k(meas, pred_yaw, pred_ay)
        baseline_rmse_rad = rmse(meas - pred_yaw)
        print(f"{plat_dir.name}: k={k:+.5f} 1/(m/s²); pooled RMSE ψ̇ "
              f"{baseline_rmse_rad*180/math.pi:.4f} → {fit_rmse_rad*180/math.pi:.4f} °/s")
        # Write corrected CSVs
        for c in csvs:
            df = pd.read_csv(c)
            df["yaw_rate_pred_rads"] = df["yaw_rate_pred_rads"] * (1.0 - k * np.abs(df["a_y_pred_mps2"]))
            df["yaw_rate_resid_rads"] = df["yaw_rate_meas_rads"] - df["yaw_rate_pred_rads"]
            df["a_y_resid_mps2"] = df["a_lat_meas_mps2"] - df["a_y_pred_mps2"]
            rel = c.relative_to(in_dir)
            target = out_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(target, index=False, float_format="%.10g")


if __name__ == "__main__":
    main()
