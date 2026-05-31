"""V2: add more features, see if RMSE drops materially."""
import glob
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]
TRUTH = "yaw_rate_meas_rads"

rng = np.random.default_rng(42)


def collect(paths):
    chunks = []
    for p in paths:
        try:
            df = pd.read_csv(p, usecols=["v_mps", "yaw_rate_pred_rads", TRUTH, "a_long_mps2", "delta_road_rad"])
        except Exception:
            continue
        m = df["v_mps"] > 2.0
        if m.sum() == 0:
            continue
        chunks.append(df.loc[m, ["v_mps", "yaw_rate_pred_rads", TRUTH, "a_long_mps2", "delta_road_rad"]].to_numpy())
    if not chunks:
        return None
    return np.vstack(chunks)


def fit(X, yt):
    coef, *_ = np.linalg.lstsq(X, yt, rcond=None)
    pred = X @ coef
    return coef, float(np.sqrt(np.mean((pred - yt) ** 2)))


for plat in PLATFORMS:
    paths = sorted(glob.glob(str(ROOT / "data" / "sim" / "segments" / plat / "*" / "**" / "sim.csv"), recursive=True))
    arr = collect(paths)
    if arr is None:
        continue
    v, y0, yt, al, dr = arr.T

    # V1 = baseline
    X1 = np.column_stack([y0, y0*v, y0*v**2, np.ones_like(y0)])
    c1, r1 = fit(X1, yt)

    # V2a: add y0*a_long, y0*|y0| (curvature stiffening?), dr-based
    X2 = np.column_stack([y0, y0*v, y0*v**2, y0*al, y0*np.abs(y0), np.ones_like(y0)])
    c2, r2 = fit(X2, yt)

    # V2b: even richer — y0*v*dr, dr alone, a_long
    X3 = np.column_stack([y0, y0*v, y0*v**2, y0*al, y0*np.abs(y0)*v, np.ones_like(y0)])
    c3, r3 = fit(X3, yt)

    # V2c: y0/(1+K*v^2) nonlinear with offset+scale (best of earlier exploration)
    from scipy.optimize import minimize
    def loss(params):
        a, K, b, c_al = params
        pred = a * y0 / (1 + K * v ** 2) + b + c_al * y0 * al
        return float(np.mean((pred - yt) ** 2))
    r = minimize(loss, x0=[1.0, 0.001, 0.0, 0.0], method="Nelder-Mead", options={"xatol":1e-6,"fatol":1e-10,"maxiter":2000})
    a, K, b, c_al = r.x
    pred_nl = a * y0 / (1 + K * v ** 2) + b + c_al * y0 * al
    r_nl = float(np.sqrt(np.mean((pred_nl - yt) ** 2)))

    print(f"\n{plat}: n={len(v):,}")
    print(f"  V1 (4 feat): {r1:.6f}")
    print(f"  V2a (+a_long, +|y0|): {r2:.6f}")
    print(f"  V2b (+a_long, +|y0|*v): {r3:.6f}")
    print(f"  V2c nonlinear (a/[1+Kv^2]+b+c*y0*al): {r_nl:.6f}  a={a:.4f}, K={K:.5f}, b={b:+.5e}, c_al={c_al:+.5e}")
