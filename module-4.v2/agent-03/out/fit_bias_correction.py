"""V3: fit a per-platform residual correction on top of V2.

Model: yr_v3 = yr_v2 + a * (v * yr_v2) + b
where a, b are per platform, fit by least squares on the residual.
"""
from __future__ import annotations
import sys, glob, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "out"))
from predict_v2 import predict as predict_v2

def collect(plat, limit=300, v_thresh=2.0):
    paths = sorted(glob.glob(str(ROOT / f"data/sim/segments/{plat}/*/*/*/sim.csv")))[:limit]
    Rs, Vs, Ys = [], [], []
    for p in paths:
        df = pd.read_csv(p, usecols=["t_s","delta_road_rad","v_mps","yaw_rate_meas_rads","yaw_rate_pred_rads"])
        out = predict_v2(df, plat)
        yr_v2 = out["yaw_rate_pred_rads"].to_numpy()
        yt = df["yaw_rate_meas_rads"].to_numpy()
        v  = df["v_mps"].to_numpy()
        resid = yt - yr_v2
        mask = v > v_thresh
        Rs.append(resid[mask]); Vs.append(v[mask]); Ys.append(yr_v2[mask])
    return np.concatenate(Rs), np.concatenate(Vs), np.concatenate(Ys)

corrs = {}
for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]:
    R, V, Y = collect(plat)
    # Features: 1, v*yr_v2 (= ay_pred). Solve: R ~ a*ay + b
    AY = V * Y
    A = np.column_stack([AY, np.ones_like(AY)])
    coef, *_ = np.linalg.lstsq(A, R, rcond=None)
    a_coef, b_coef = float(coef[0]), float(coef[1])
    # Residual after correction
    R_after = R - (a_coef * AY + b_coef)
    rmse_before = float(np.sqrt((R*R).mean()))
    rmse_after = float(np.sqrt((R_after*R_after).mean()))
    print(f"{plat:30s} a={a_coef:+.5f} b={b_coef:+.6f} | rmse {rmse_before:.6f} -> {rmse_after:.6f}")
    corrs[plat] = dict(a_ay=a_coef, b=b_coef)

with open(ROOT / "out" / "v3_correction.json", "w") as f:
    json.dump(corrs, f, indent=2)
print("Wrote v3_correction.json")
