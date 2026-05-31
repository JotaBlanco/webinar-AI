"""Explore speed dependence of correction."""
import glob
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]
TRUTH = "yaw_rate_meas_rads"


def load(platform, n=300):
    paths = sorted(glob.glob(str(ROOT / "data" / "sim" / "segments" / platform / "*" / "**" / "sim.csv"), recursive=True))[:n]
    return pd.concat([pd.read_csv(p) for p in paths], ignore_index=True)


for plat in PLATFORMS:
    df = load(plat, 300)
    m = df["v_mps"] > 2.0
    yv0 = df.loc[m, "yaw_rate_pred_rads"].to_numpy()
    yt = df.loc[m, TRUTH].to_numpy()
    v = df.loc[m, "v_mps"].to_numpy()

    # Feature set: y_v0, y_v0 * v^2, y_v0 * v, 1
    # Justified by bicycle-model understeer gain ~ 1 / (1 + Kus * v^2)
    # So truth ~ y_v0 / (1 + K*v^2) ≈ y_v0 - K*v^2*y_v0 to first order.
    X = np.column_stack([yv0, yv0 * v, yv0 * v**2, np.ones_like(yv0)])
    coef, *_ = np.linalg.lstsq(X, yt, rcond=None)
    pred = X @ coef
    rmse = float(np.sqrt(np.mean((pred - yt) ** 2)))
    bias = float(np.mean(pred - yt))
    print(f"\n{plat}:")
    print(f"  coef = a0={coef[0]:.4f}, a1*v={coef[1]:.5e}, a2*v^2={coef[2]:.5e}, b={coef[3]:+.5e}")
    print(f"  RMSE = {rmse:.5f}, bias = {bias:+.6f}")

    # Simpler: y_v0 / (1+K*v^2)  — nonlinear, do scipy
    from scipy.optimize import minimize_scalar
    def loss(K):
        return float(np.mean((yt - yv0 / (1 + K * v ** 2)) ** 2))
    res = minimize_scalar(loss, bounds=(-0.005, 0.02), method="bounded")
    K = res.x
    pred_us = yv0 / (1 + K * v ** 2)
    rmse_us = float(np.sqrt(np.mean((pred_us - yt) ** 2)))
    bias_us = float(np.mean(pred_us - yt))
    print(f"  Understeer K={K:.5f} 1/(m/s)^2, RMSE={rmse_us:.5f}, bias={bias_us:+.6f}")

    # Understeer K plus delta offset: y_v0_corr = (v/L)*tan(delta_road + d0) -- but we don't have L here
    # Use scale a and offset on yaw: yt ~ a * yv0 / (1 + K*v^2) + b
    from scipy.optimize import minimize
    def loss2(params):
        a, K, b = params
        return float(np.mean((yt - (a * yv0 / (1 + K * v ** 2) + b)) ** 2))
    r = minimize(loss2, x0=[1.0, 0.001, 0.0], method="Nelder-Mead")
    a, K, b = r.x
    pred3 = a * yv0 / (1 + K * v ** 2) + b
    rmse3 = float(np.sqrt(np.mean((pred3 - yt) ** 2)))
    bias3 = float(np.mean(pred3 - yt))
    print(f"  Understeer+scale+offset: a={a:.4f}, K={K:.5f}, b={b:+.5e}, RMSE={rmse3:.5f}, bias={bias3:+.6f}")
