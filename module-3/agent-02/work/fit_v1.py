"""Fit per-platform (g, delta0, K_us, tau) on TRAIN, validate on DEV.

Model:
  yaw_rate_pred(t) = LP_tau{ v * (g*delta + delta0) / (L + K_us * v^2) }

Fit by minimising pooled MSE over samples with v > 2 m/s on TRAIN segments.
"""
import sys, os
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

# Parameters from openpilot priors:
L_BY_PLATFORM = {
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
}

train, dev = split(dev_fraction=0.25, seed=42)

# Group by platform.
def platform_of(p):
    return Path(p).resolve().parents[3].name

train_by_plat = {}
for p in train:
    pl = platform_of(p)
    train_by_plat.setdefault(pl, []).append(p)


def load_concat(paths):
    """Concatenate sim data with a 'seg' id column so we can avoid mixing residuals across segments."""
    frames = []
    for i, p in enumerate(paths):
        df = pd.read_csv(p)
        df["_seg"] = i
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def steady_state_yaw(delta, v, g, delta0, K_us, L):
    """Steady-state yaw rate, bicycle: v*(g*delta + delta0) / (L + K_us*v^2)."""
    return v * (g * delta + delta0) / (L + K_us * v * v)


def apply_lag(yr_ss, dt, tau):
    """First-order lag: y[k+1] = y[k] + (dt/tau)*(yr_ss[k] - y[k]). dt scalar or array of len n-1."""
    n = len(yr_ss)
    y = np.empty(n)
    y[0] = yr_ss[0]
    if tau <= 1e-6:
        return yr_ss.copy()
    if np.isscalar(dt):
        a = dt / tau
        for k in range(n - 1):
            y[k + 1] = y[k] + a * (yr_ss[k] - y[k])
    else:
        for k in range(n - 1):
            a = dt[k] / tau
            y[k + 1] = y[k] + a * (yr_ss[k] - y[k])
    return y


def fit_platform(paths, L, init=(1.0, 0.0, 0.003, 0.06)):
    """Fit (g, delta0, K_us, tau) for one platform across segments."""
    # Pre-load all segments as a list of (delta, v, yr_truth, dt_array) tuples.
    segs = []
    for p in paths:
        df = pd.read_csv(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        t = df["t_s"].to_numpy(float)
        v = df["v_mps"].to_numpy(float)
        delta = df["delta_road_rad"].to_numpy(float)
        yr = df["yaw_rate_meas_rads"].to_numpy(float)
        if len(t) < 5 or np.any(np.diff(t) <= 0):
            continue
        dt = np.diff(t)
        mask = v > 2.0
        if not mask.any():
            continue
        segs.append((delta, v, yr, dt, mask))

    def objective(params):
        g, delta0, K_us, tau = params
        if tau <= 0 or K_us < -1e-3:
            return 1e9
        total_sq = 0.0
        n_total = 0
        for delta, v, yr, dt, mask in segs:
            yr_ss = steady_state_yaw(delta, v, g, delta0, K_us, L)
            yr_pred = apply_lag(yr_ss, dt, tau)
            r = yr_pred[mask] - yr[mask]
            total_sq += float(np.sum(r * r))
            n_total += int(mask.sum())
        return total_sq / max(n_total, 1)

    res = minimize(
        objective,
        x0=list(init),
        method="Nelder-Mead",
        options={"xatol": 1e-5, "fatol": 1e-10, "maxiter": 600, "disp": False},
    )
    return res.x, res.fun


# Fit each platform on TRAIN.
fitted = {}
for plat, paths in train_by_plat.items():
    L = L_BY_PLATFORM[plat]
    params, fun = fit_platform(paths, L)
    g, d0, K, tau = params
    print(f"[{plat}] g={g:.4f} delta0={d0:.5f} K_us={K:.5f} tau={tau:.4f}  obj={fun:.6e}")
    fitted[plat] = dict(g=g, delta0=d0, K_us=K, tau=tau, L=L)

import json
with open(ROOT / "work" / "fitted_v1.json", "w") as fh:
    json.dump(fitted, fh, indent=2)


# Build a predict callable using fitted params; then score on dev + train.
def make_predict_fn(fitted):
    def predict(sim_df, platform):
        out = pd.DataFrame(index=sim_df.index)
        if platform not in fitted:
            # Tesla: V0 passthrough
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
        yr_ss = steady_state_yaw(delta, v, p["g"], p["delta0"], p["K_us"], p["L"])
        yr_pred = apply_lag(yr_ss, dt, p["tau"])
        out["yaw_rate_pred_rads"] = yr_pred
        return out
    return predict


predict_fn = make_predict_fn(fitted)

print("\n=== V1 on DEV ===")
res = score(predict_fn, segment_paths=dev)
print(f"yaw_rate_rmse: {res['yaw_rate_rmse']:.6f}")
print(f"cte_rmse:      {res['cte_rmse']:.4f}")
print(f"per_platform:  {res['per_platform']}")
print(f"per_regime:    {res['per_regime']}")

print("\n=== V1 on TRAIN ===")
res = score(predict_fn, segment_paths=train)
print(f"yaw_rate_rmse: {res['yaw_rate_rmse']:.6f}")
print(f"cte_rmse:      {res['cte_rmse']:.4f}")
print(f"per_platform:  {res['per_platform']}")
