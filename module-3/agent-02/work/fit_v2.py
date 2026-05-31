"""V2: V1 model + complementary filter blending with a_lat-derived yaw rate.

yr_alat = a_lat / v (when v large enough)
yr_blend = (1-alpha) * yr_model + alpha * yr_alat_filtered

Also test polynomial steering scale: g(delta) = g0 + g1 * |delta|.

Fit per platform.
"""
import sys, os, json
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-02")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "skills" / "make-train-dev-split"))
os.chdir(ROOT)

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from score import score
from split import split

L_BY_PLATFORM = {
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
}

train, dev = split(dev_fraction=0.25, seed=42)

def platform_of(p):
    return Path(p).resolve().parents[3].name

train_by_plat = {}
for p in train:
    pl = platform_of(p)
    train_by_plat.setdefault(pl, []).append(p)


def apply_lag(yr_ss, dt, tau):
    n = len(yr_ss)
    y = np.empty(n)
    y[0] = yr_ss[0]
    if tau <= 1e-6:
        return yr_ss.copy()
    for k in range(n - 1):
        a = dt[k] / tau
        y[k + 1] = y[k] + a * (yr_ss[k] - y[k])
    return y


def model_yr(delta, v, g0, g1, delta0, K_us, L, tau, dt):
    """Polynomial steering scale + understeer + first-order lag."""
    g_eff = g0 + g1 * np.abs(delta)
    yr_ss = v * (g_eff * delta + delta0) / (L + K_us * v * v)
    return apply_lag(yr_ss, dt, tau)


def fit_platform_v2(paths, L):
    segs = []
    for p in paths:
        df = pd.read_csv(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        t = df["t_s"].to_numpy(float)
        v = df["v_mps"].to_numpy(float)
        delta = df["delta_road_rad"].to_numpy(float)
        yr = df["yaw_rate_meas_rads"].to_numpy(float)
        a_lat = df["a_lat_meas_mps2"].to_numpy(float) if "a_lat_meas_mps2" in df.columns else None
        if len(t) < 5 or np.any(np.diff(t) <= 0):
            continue
        dt = np.diff(t)
        mask = v > 2.0
        if not mask.any():
            continue
        segs.append((delta, v, yr, dt, mask, a_lat))

    def predict_model(params):
        g0, g1, delta0, K_us, tau, alpha = params
        results = []
        for delta, v, yr, dt, mask, a_lat in segs:
            ym = model_yr(delta, v, g0, g1, delta0, K_us, L, tau, dt)
            if a_lat is not None and alpha > 0:
                # a_lat / v ; avoid div by zero
                vs = np.where(v > 1.0, v, 1.0)
                yr_alat = a_lat / vs
                # smooth a_lat with same tau to align dynamics
                yr_alat_f = apply_lag(yr_alat, dt, tau)
                y = (1 - alpha) * ym + alpha * yr_alat_f
            else:
                y = ym
            results.append((y, yr, mask))
        return results

    def objective(params):
        g0, g1, delta0, K_us, tau, alpha = params
        if tau <= 0 or K_us < -1e-3 or alpha < 0 or alpha > 1:
            return 1e9
        results = predict_model(params)
        total_sq = 0.0
        n = 0
        for y, yr, mask in results:
            r = y[mask] - yr[mask]
            total_sq += float(np.sum(r * r))
            n += int(mask.sum())
        return total_sq / max(n, 1)

    # Init with V1 result
    init = [1.0, 0.0, 0.0, 0.003, 0.06, 0.0]
    res = minimize(objective, x0=init, method="Nelder-Mead",
                   options={"xatol": 1e-5, "fatol": 1e-10, "maxiter": 1200, "disp": False})
    return res.x, res.fun


fitted = {}
for plat, paths in train_by_plat.items():
    L = L_BY_PLATFORM[plat]
    params, fun = fit_platform_v2(paths, L)
    g0, g1, d0, K, tau, alpha = params
    print(f"[{plat}] g0={g0:.4f} g1={g1:.4f} delta0={d0:.5f} K_us={K:.5f} tau={tau:.4f} alpha={alpha:.4f}  obj={fun:.6e}")
    fitted[plat] = dict(g0=g0, g1=g1, delta0=d0, K_us=K, tau=tau, alpha=alpha, L=L)

with open(ROOT / "work" / "fitted_v2.json", "w") as fh:
    json.dump(fitted, fh, indent=2)


def make_predict_fn(fitted):
    def predict(sim_df, platform):
        out = pd.DataFrame(index=sim_df.index)
        if platform not in fitted:
            if "yaw_rate_pred_rads" in sim_df.columns:
                out["yaw_rate_pred_rads"] = sim_df["yaw_rate_pred_rads"]
            else:
                out["yaw_rate_pred_rads"] = 0.0
            return out
        p = fitted[platform]
        t = sim_df["t_s"].to_numpy(float)
        v = sim_df["v_mps"].to_numpy(float)
        delta = sim_df["delta_road_rad"].to_numpy(float)
        if len(t) < 2:
            out["yaw_rate_pred_rads"] = 0.0
            return out
        dt = np.diff(t)
        ym = model_yr(delta, v, p["g0"], p["g1"], p["delta0"], p["K_us"], p["L"], p["tau"], dt)
        a_lat = sim_df["a_lat_meas_mps2"].to_numpy(float) if "a_lat_meas_mps2" in sim_df.columns else None
        if a_lat is not None and p["alpha"] > 0:
            vs = np.where(v > 1.0, v, 1.0)
            yr_alat = a_lat / vs
            yr_alat_f = apply_lag(yr_alat, dt, p["tau"])
            y = (1 - p["alpha"]) * ym + p["alpha"] * yr_alat_f
        else:
            y = ym
        out["yaw_rate_pred_rads"] = y
        return out
    return predict


predict_fn = make_predict_fn(fitted)

print("\n=== V2 on DEV ===")
res = score(predict_fn, segment_paths=dev)
print(f"yaw_rate_rmse: {res['yaw_rate_rmse']:.6f}")
print(f"cte_rmse:      {res['cte_rmse']:.4f}")
print(f"per_platform:  {res['per_platform']}")
print(f"per_regime:    {res['per_regime']}")

print("\n=== V2 on TRAIN ===")
res = score(predict_fn, segment_paths=train)
print(f"yaw_rate_rmse: {res['yaw_rate_rmse']:.6f}")
print(f"cte_rmse:      {res['cte_rmse']:.4f}")
print(f"per_platform:  {res['per_platform']}")
