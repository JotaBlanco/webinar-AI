"""Quick CV check: train V3 correction on first half, test on second half of segments."""
from __future__ import annotations
import sys, glob, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "out"))
from predict_v2 import predict as predict_v2

def collect(plat, paths, v_thresh=2.0):
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
    if not Rs: return None
    return np.concatenate(Rs), np.concatenate(Vs), np.concatenate(Ys)

for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]:
    all_paths = sorted(glob.glob(str(ROOT / f"data/sim/segments/{plat}/*/*/*/sim.csv")))
    n = len(all_paths)
    # Shuffle deterministically by sorted name, take train = even-indexed, test = odd-indexed
    train = [p for i,p in enumerate(all_paths) if i % 2 == 0][:300]
    test  = [p for i,p in enumerate(all_paths) if i % 2 == 1][:300]
    print(f"\n{plat}: train={len(train)} test={len(test)}")
    R_tr, V_tr, Y_tr = collect(plat, train)
    R_te, V_te, Y_te = collect(plat, test)
    AY_tr = V_tr * Y_tr
    AY_te = V_te * Y_te
    A_tr = np.column_stack([AY_tr, np.ones_like(AY_tr)])
    coef, *_ = np.linalg.lstsq(A_tr, R_tr, rcond=None)
    a, b = coef
    R_tr_after = R_tr - (a * AY_tr + b)
    R_te_after = R_te - (a * AY_te + b)
    rmse_tr_b = float(np.sqrt((R_tr*R_tr).mean()))
    rmse_tr_a = float(np.sqrt((R_tr_after*R_tr_after).mean()))
    rmse_te_b = float(np.sqrt((R_te*R_te).mean()))
    rmse_te_a = float(np.sqrt((R_te_after*R_te_after).mean()))
    print(f"  train rmse: {rmse_tr_b:.6f} -> {rmse_tr_a:.6f}")
    print(f"  test  rmse: {rmse_te_b:.6f} -> {rmse_te_a:.6f}  (a={a:+.5f} b={b:+.6f})")
