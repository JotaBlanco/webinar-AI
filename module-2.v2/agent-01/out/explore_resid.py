"""Explore residual structure per platform."""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]
TRUTH = "yaw_rate_meas_rads"

def load_concat(platform, max_segments=80):
    paths = sorted(glob.glob(str(ROOT / "data" / "sim" / "segments" / platform / "*" / "**" / "sim.csv"), recursive=True))[:max_segments]
    frames = []
    for p in paths:
        df = pd.read_csv(p)
        df["__path"] = p
        frames.append(df)
    return pd.concat(frames, ignore_index=True)

for plat in PLATFORMS:
    df = load_concat(plat, 200)
    m = df["v_mps"] > 2.0
    yv0 = df.loc[m, "yaw_rate_pred_rads"].to_numpy()
    yt  = df.loc[m, TRUTH].to_numpy()
    v   = df.loc[m, "v_mps"].to_numpy()
    dr  = df.loc[m, "delta_road_rad"].to_numpy()
    res = yt - yv0  # what we need to add to V0 to recover truth

    # Affine fit: yaw_truth ~ a * yaw_v0 + b
    A = np.column_stack([yv0, np.ones_like(yv0)])
    coef, *_ = np.linalg.lstsq(A, yt, rcond=None)
    a, b = coef
    pred_lin = A @ coef
    rmse_lin = float(np.sqrt(np.mean((pred_lin - yt)**2)))

    # Affine with offset on delta: yt ~ k * (v/L) * tan(dr + d0)
    # Approx linear: yt ~ k * (v/L) * (dr + d0)  -> regress on x1 = (v/L)*dr, x2 = (v/L)
    # We don't know L precisely; use 1 to absorb in coefficient.
    x1 = v * dr  # proxy for v*delta
    A2 = np.column_stack([x1, v, np.ones_like(v)])
    coef2, *_ = np.linalg.lstsq(A2, yt, rcond=None)
    pred2 = A2 @ coef2
    rmse2 = float(np.sqrt(np.mean((pred2 - yt)**2)))

    rmse_v0 = float(np.sqrt(np.mean((yv0 - yt)**2)))
    print(f"\n{plat}:  n_rows={len(yv0):,}")
    print(f"  V0 yaw RMSE = {rmse_v0:.5f}, mean_signed = {(yv0-yt).mean():+.5f}")
    print(f"  Affine fit yt = a*y_v0 + b: a={a:.4f}, b={b:+.5f}, RMSE={rmse_lin:.5f}")
    print(f"  Linearised KS fit (v*dr, v, 1): coef={coef2}, RMSE={rmse2:.5f}")
