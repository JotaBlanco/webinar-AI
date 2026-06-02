"""Quick diagnosis of V1 residuals."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
import importlib.util
spec = importlib.util.spec_from_file_location("v1_baseline", ROOT / "code" / "v1_baseline.py")
v1mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(v1mod)
predict_v1 = v1mod.predict_v1

PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]
data_full = ROOT / "data" / "sim" / "segments"

for plat in PLATFORMS:
    yaw_truth = []
    yaw_pred = []
    resid = []
    dd = []
    v_all = []
    yr_pred_v0 = []
    a_lat_proxy = []
    delta = []
    for sim_csv in (data_full / plat).rglob("sim.csv"):
        df = pd.read_csv(sim_csv)
        if "yaw_rate_meas_rads" not in df.columns: continue
        try:
            pred = predict_v1(df, plat)
        except Exception:
            continue
        r = df["yaw_rate_meas_rads"].to_numpy() - pred["yaw_rate_pred_rads"].to_numpy()
        t = df["t_s"].to_numpy()
        dt = np.diff(t, prepend=t[0])
        dt[dt<=0] = 0.02
        d_delta = np.gradient(df["delta_road_rad"].to_numpy(), t)
        resid.append(r)
        dd.append(d_delta)
        v_all.append(df["v_mps"].to_numpy())
        yr_pred_v0.append(df["yaw_rate_pred_rads"].to_numpy())
        a_lat_proxy.append(df["v_mps"].to_numpy() * df["yaw_rate_pred_rads"].to_numpy())
        delta.append(df["delta_road_rad"].to_numpy())
    resid = np.concatenate(resid)
    dd = np.concatenate(dd)
    v_all = np.concatenate(v_all)
    yr_pred_v0 = np.concatenate(yr_pred_v0)
    a_lat_proxy = np.concatenate(a_lat_proxy)
    delta = np.concatenate(delta)
    transient = np.abs(dd) > 0.05
    high_alat = np.abs(a_lat_proxy) > 4
    straight = np.abs(yr_pred_v0) < 0.02
    print(f"\n=== {plat} ===")
    print(f"N={len(resid)}, RMSE total={np.sqrt(np.mean(resid**2)):.5f}")
    print(f"  transient (|d_delta|>0.05): {transient.sum()/len(resid)*100:.1f}% rows, RMSE={np.sqrt(np.mean(resid[transient]**2)) if transient.sum() else 0:.5f}, sum_sq_share={(resid[transient]**2).sum()/(resid**2).sum()*100:.1f}%")
    print(f"  high_alat (|v*yr_v0|>4):    {high_alat.sum()/len(resid)*100:.1f}% rows, RMSE={np.sqrt(np.mean(resid[high_alat]**2)) if high_alat.sum() else 0:.5f}, sum_sq_share={(resid[high_alat]**2).sum()/(resid**2).sum()*100:.1f}%")
    print(f"  straight  (|yr_v0|<0.02):   {straight.sum()/len(resid)*100:.1f}% rows, RMSE={np.sqrt(np.mean(resid[straight]**2)) if straight.sum() else 0:.5f}, sum_sq_share={(resid[straight]**2).sum()/(resid**2).sum()*100:.1f}%")
    print(f"  mean residual (bias): {resid.mean():.5f}")
    # correlations
    feats = {"d_delta": dd, "v": v_all, "yr_v0": yr_pred_v0, "delta": delta, "a_lat_proxy": a_lat_proxy, "v*d_delta": v_all*dd}
    for fn, fv in feats.items():
        m = np.isfinite(fv)
        c = np.corrcoef(resid[m], fv[m])[0,1]
        print(f"  corr(resid, {fn})={c:+.3f}")
