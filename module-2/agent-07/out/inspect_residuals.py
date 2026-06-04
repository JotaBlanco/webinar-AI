"""Quick residual diagnostic on each platform after V1+V2 fit."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-07")
sys.path.insert(0, str(ROOT / "final-model"))
from predict import predict  # noqa

TRUTH = {
    "FORD_F_150_LIGHTNING_MK1": "yaw_rate_meas_rads",
    "FORD_MUSTANG_MACH_E_MK1":  "yaw_rate_meas_rads",
    "HYUNDAI_IONIQ_5":          "yaw_rate_meas_rads",
}

def collect(plat: str, max_segs: int = 60):
    paths = sorted((ROOT / "data" / "sim" / "segments" / plat).glob("*/**/sim.csv"))[:max_segs]
    R, V, D, DD, A = [], [], [], [], []
    for p in paths:
        df = pd.read_csv(p)
        if TRUTH[plat] not in df.columns: continue
        out = predict(df, plat)
        t = df["t_s"].to_numpy(float)
        v = df["v_mps"].to_numpy(float)
        d = df["delta_road_rad"].to_numpy(float)
        a = df["a_long_mps2"].to_numpy(float) if "a_long_mps2" in df.columns else np.zeros_like(t)
        if np.any(np.diff(t) <= 0): continue
        dd = np.gradient(d, t)
        resid = out["yaw_rate_pred_rads"].to_numpy(float) - df[TRUTH[plat]].to_numpy(float)
        mask = v > 2.0
        R.append(resid[mask]); V.append(v[mask]); D.append(d[mask])
        DD.append(dd[mask]); A.append(a[mask])
    return tuple(np.concatenate(x) for x in (R, V, D, DD, A))


def autocorr(x, lag):
    x = x - x.mean()
    return float(np.mean(x[:-lag] * x[lag:]) / (x.var() + 1e-12))


for plat in TRUTH:
    R, V, D, DD, A = collect(plat)
    print(f"\n== {plat}: n={len(R):,}, rmse={np.sqrt((R**2).mean()):.5f}, bias={R.mean():+.5f}")
    print(f"  corr(resid, v)   = {np.corrcoef(R, V)[0,1]:+.3f}")
    print(f"  corr(resid, v²)  = {np.corrcoef(R, V*V)[0,1]:+.3f}")
    print(f"  corr(resid, δ)   = {np.corrcoef(R, D)[0,1]:+.3f}")
    print(f"  corr(resid, |δ|) = {np.corrcoef(R, np.abs(D))[0,1]:+.3f}")
    print(f"  corr(resid, dδ)  = {np.corrcoef(R, DD)[0,1]:+.3f}")
    print(f"  corr(resid, v·δ) = {np.corrcoef(R, V*D)[0,1]:+.3f}")
    print(f"  corr(resid, v²δ) = {np.corrcoef(R, V*V*D)[0,1]:+.3f}")
    print(f"  corr(resid, a)   = {np.corrcoef(R, A)[0,1]:+.3f}")
    print(f"  autocorr lag-1   = {autocorr(R, 1):+.3f}")
    print(f"  autocorr lag-3   = {autocorr(R, 3):+.3f}")
    print(f"  autocorr lag-6   = {autocorr(R, 6):+.3f}")
