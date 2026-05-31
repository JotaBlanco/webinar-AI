"""V2: add polynomial steering (g0 + g1*|delta|*delta cubic asymmetric, or quadratic in delta).

Model: delta_eff = g0*delta + g2*delta*|delta| + delta0  (odd nonlinear)
yr_ss = v * delta_eff / (L_eff + K_us * v^2)
yr filtered with first-order lag tau.

Plus speed-dependent K_us option: K_us(v) = K0 + K1*v.
"""
import sys, os, json
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-03")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "skills" / "make-train-dev-split"))
sys.path.insert(0, str(ROOT / "_shared"))

import numpy as np
import pandas as pd
from scipy.optimize import least_squares
from split import split


def first_order_lag(yr_ss: np.ndarray, t: np.ndarray, tau: float) -> np.ndarray:
    if tau <= 1e-6:
        return yr_ss.copy()
    y = np.empty_like(yr_ss)
    y[0] = yr_ss[0]
    dt = np.diff(t)
    a = np.exp(-dt / tau)
    for k in range(len(dt)):
        y[k + 1] = a[k] * y[k] + (1.0 - a[k]) * yr_ss[k + 1]
    return y


def load_cache(paths):
    cached = []
    for p in paths:
        df = pd.read_csv(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        t = df["t_s"].to_numpy(float)
        if len(t) < 5 or np.any(np.diff(t) <= 0):
            continue
        v = df["v_mps"].to_numpy(float)
        delta = df["delta_road_rad"].to_numpy(float)
        yr_meas = df["yaw_rate_meas_rads"].to_numpy(float)
        mask = v > 3.0
        if mask.sum() < 50:
            continue
        cached.append((t, v, delta, yr_meas, mask))
    return cached


def fit_v2(cached, x0):
    """7 params: g0, g2, delta0, L_eff, K0, K1, tau"""
    def residuals(theta):
        g0, g2, delta0, L_eff, K0, K1, tau = theta
        if L_eff <= 0.5 or tau < 0 or tau > 0.5:
            return np.full(1000, 1e3)
        res_chunks = []
        for t, v, delta, yr_meas, mask in cached:
            delta_eff = g0 * delta + g2 * delta * np.abs(delta) + delta0
            K_eff = K0 + K1 * v
            yr_ss = v * delta_eff / (L_eff + K_eff * v * v)
            yr_pred = first_order_lag(yr_ss, t, tau)
            r = (yr_pred - yr_meas)[mask]
            res_chunks.append(r)
        return np.concatenate(res_chunks)

    lb = np.array([0.5, -2.0, -0.02, 1.5, -0.005, -0.001, 0.0])
    ub = np.array([1.5,  2.0,  0.02, 6.0,  0.02,   0.001, 0.3])
    res = least_squares(residuals, x0, bounds=(lb, ub), method='trf', max_nfev=300, verbose=1)
    return res.x, np.sqrt(np.mean(res.fun**2))


if __name__ == "__main__":
    train, dev = split()
    by_plat_train = {"FORD_F_150_LIGHTNING_MK1": [], "FORD_MUSTANG_MACH_E_MK1": []}
    for p in train:
        for k in by_plat_train:
            if k in str(p):
                by_plat_train[k].append(p)

    params_by_platform = {}
    for plat, paths in by_plat_train.items():
        print(f"\n=== {plat} train segs: {len(paths)} ===")
        cached = load_cache(paths)
        print(f"  usable: {len(cached)}")
        L0 = 2.984 if "MACH_E" in plat else 3.70
        x0 = np.array([1.0, 0.0, 0.0, L0, 0.002, 0.0, 0.06])
        x, rmse = fit_v2(cached, x0)
        g0, g2, delta0, L_eff, K0, K1, tau = x
        print(f"  g0={g0:.4f}  g2={g2:.4f}  d0={delta0:.5f}  L_eff={L_eff:.3f}  K0={K0:.5f}  K1={K1:.6f}  tau={tau:.4f}  RMSE={rmse:.5f}")
        params_by_platform[plat] = dict(g0=float(g0), g2=float(g2), delta0=float(delta0),
                                         L_eff=float(L_eff), K0=float(K0), K1=float(K1), tau=float(tau))

    out = ROOT / "work" / "params_v2.json"
    out.write_text(json.dumps(params_by_platform, indent=2))
    print("\nWrote", out)
