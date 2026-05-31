"""Look at yaw residual vs features for Hyundai/Mach-E on worst segments."""
from __future__ import annotations
import os, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-08")
os.chdir(str(ROOT))

# residual after v1 model
import json
coeffs = json.loads((ROOT / "out" / "coeffs_v1.json").read_text())

def pred_v1(df, plat):
    c = coeffs.get(plat, {"G":1, "Kus":0, "bias":0})
    v = df["v_mps"].to_numpy(dtype=float)
    yv0 = df["yaw_rate_pred_rads"].to_numpy(dtype=float)
    return (c["G"] * yv0) / (1.0 + c["Kus"] * v * v) + c["bias"]


for plat in ("FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"):
    root = ROOT / "data" / "sim" / "segments" / plat
    paths = list(root.glob("**/sim.csv"))
    # Collect residuals across all segs (subsample for speed)
    res, v_all, yv0_all, delta_all, ay_all = [], [], [], [], []
    for p in paths[:60]:
        df = pd.read_csv(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        v = df["v_mps"].to_numpy(dtype=float)
        yv0 = df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        truth = df["yaw_rate_meas_rads"].to_numpy(dtype=float)
        # Apply v1 model
        c = coeffs[plat]
        pred = (c["G"] * yv0) / (1.0 + c["Kus"] * v * v) + c["bias"]
        r = pred - truth
        mask = v > 2.0
        res.append(r[mask])
        v_all.append(v[mask])
        yv0_all.append(yv0[mask])
        delta_all.append(df["delta_road_rad"].to_numpy(dtype=float)[mask])
        if "a_lat_meas_mps2" in df.columns:
            ay_all.append(df["a_lat_meas_mps2"].to_numpy(dtype=float)[mask])
    r = np.concatenate(res)
    v = np.concatenate(v_all)
    yv0 = np.concatenate(yv0_all)
    delta = np.concatenate(delta_all)
    print(f"\n=== {plat} (n={len(r)}) ===")
    print(f"  mean resid: {r.mean():+.5f}, std: {r.std():.5f}")
    # bin by v
    print("  by v:")
    edges = [0, 5, 10, 15, 20, 25, 30, 40]
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (v >= lo) & (v < hi)
        if m.sum() > 100:
            print(f"    v in [{lo:2d},{hi:2d}): mean={r[m].mean():+.5f} std={r[m].std():.5f} n={m.sum()}")
    # bin by |delta_road|
    print("  by |delta|:")
    dabs = np.abs(delta)
    edges = [0, 0.005, 0.01, 0.02, 0.05, 0.1, 0.5]
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (dabs >= lo) & (dabs < hi)
        if m.sum() > 100:
            print(f"    |d| in [{lo:.3f},{hi:.3f}): mean={r[m].mean():+.5f} std={r[m].std():.5f} n={m.sum()}")
    # bin by yv0 sign
    print("  by yv0 sign:")
    for label, m in (("yv0 > 0.05", yv0 > 0.05), ("yv0 < -0.05", yv0 < -0.05), ("|yv0|<0.01", np.abs(yv0)<0.01)):
        if m.sum() > 100:
            print(f"    {label}: mean={r[m].mean():+.5f} std={r[m].std():.5f} n={m.sum()}")
