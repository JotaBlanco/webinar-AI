"""Quick residual structure look-see for V1 by platform."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import importlib.util as _iu
_spec = _iu.spec_from_file_location("v1b", ROOT/"code"/"v1_baseline.py")
_v1m = _iu.module_from_spec(_spec); _spec.loader.exec_module(_v1m)
predict_v1 = _v1m.predict_v1

ALLOWLIST = ["t_s","delta_wheel_deg","delta_road_rad","v_mps","a_long_mps2","accel_pedal_pct","brake_pressed","yaw_rate_pred_rads"]

def gather(platform, n=200):
    pdir = ROOT/"data"/"sim"/"segments"/platform
    rows = []
    csvs = list(pdir.rglob("sim.csv"))[:n]
    for c in csvs:
        df = pd.read_csv(c)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        out = predict_v1(df[ALLOWLIST], platform)
        df["yr_v1"] = out["yaw_rate_pred_rads"].values
        df["yr_truth"] = df["yaw_rate_meas_rads"]
        df["res"] = df["yr_truth"] - df["yr_v1"]
        rows.append(df)
    if not rows: return None
    return pd.concat(rows, ignore_index=True)

for plat in ["FORD_F_150_LIGHTNING_MK1","FORD_MUSTANG_MACH_E_MK1","HYUNDAI_IONIQ_5"]:
    d = gather(plat, n=100)
    if d is None or len(d)==0:
        print(plat, "no data"); continue
    r = d["res"].values
    print(f"\n=== {plat} (n_samples={len(d)}) ===")
    print(f"res mean={r.mean():.5f} std={r.std():.5f} rmse={np.sqrt((r**2).mean()):.5f}")
    # corr of residual with features
    for col in ["delta_road_rad","v_mps","a_long_mps2","yr_v1"]:
        c = d[col].values
        m = np.isfinite(c) & np.isfinite(r)
        if m.sum() < 10: continue
        cor = np.corrcoef(c[m], r[m])[0,1]
        print(f"  corr(res, {col}) = {cor:+.3f}")
    # check lateral acc proxy
    lat = d["v_mps"].values * d["yr_v1"].values
    cor = np.corrcoef(lat, r)[0,1]
    print(f"  corr(res, v*yr_v1) = {cor:+.3f}")
    # v*delta
    vd = d["v_mps"].values * d["delta_road_rad"].values
    cor = np.corrcoef(vd, r)[0,1]
    print(f"  corr(res, v*delta) = {cor:+.3f}")
    # yr_v1 itself (slope error)
    print(f"  corr(res, yr_v1) = {np.corrcoef(d['yr_v1'].values, r)[0,1]:+.3f}")
    # delta derivative (rate effect)
    dd = np.gradient(d["delta_road_rad"].values)
    cor = np.corrcoef(dd, r)[0,1]
    print(f"  corr(res, d(delta)/dt) = {cor:+.3f}")
