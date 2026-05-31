"""Try richer linear features for per-platform fit."""
import glob
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]
TRUTH = "yaw_rate_meas_rads"


def load(platform, n=400):
    paths = sorted(glob.glob(str(ROOT / "data" / "sim" / "segments" / platform / "*" / "**" / "sim.csv"), recursive=True))[:n]
    return pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)


def fit_and_report(name, X, yt):
    coef, *_ = np.linalg.lstsq(X, yt, rcond=None)
    pred = X @ coef
    rmse = float(np.sqrt(np.mean((pred - yt) ** 2)))
    return coef, rmse


for plat in PLATFORMS:
    df = load(plat, 400)
    m = df["v_mps"] > 2.0
    yv0 = df.loc[m, "yaw_rate_pred_rads"].to_numpy()
    yt = df.loc[m, TRUTH].to_numpy()
    v = df.loc[m, "v_mps"].to_numpy()
    dr = df.loc[m, "delta_road_rad"].to_numpy()
    a_lon = df.loc[m, "a_long_mps2"].to_numpy()

    print(f"\n=== {plat} ===  n={len(yv0):,}")

    # Model A: [y_v0, y_v0*v, y_v0*v^2, 1]
    XA = np.column_stack([yv0, yv0*v, yv0*v**2, np.ones_like(yv0)])
    cA, rA = fit_and_report("A", XA, yt)
    print(f"  A: coef={cA}, rmse={rA:.6f}")

    # Model B: add y_v0 * a_long  (transient load shift)
    XB = np.column_stack([yv0, yv0*v, yv0*v**2, yv0*a_lon, np.ones_like(yv0)])
    cB, rB = fit_and_report("B", XB, yt)
    print(f"  B: coef={cB}, rmse={rB:.6f}")

    # Model C: A + interaction v*dr, dr alone
    XC = np.column_stack([yv0, yv0*v, yv0*v**2, v*dr, dr, np.ones_like(yv0)])
    cC, rC = fit_and_report("C", XC, yt)
    print(f"  C: coef={cC}, rmse={rC:.6f}")
