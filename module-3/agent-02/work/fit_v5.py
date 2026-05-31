"""V5: V3 model + per-segment steering offset estimated from straight-line driving
in the input data itself.

Idea: a vehicle going straight on average has measured a_lat ~ 0 and yaw_rate ~ 0.
The corresponding measured delta_road samples reveal a small steering-bias / centring
offset. Subtract its median from delta before feeding to the model.

This is inferable at inference time (we use a_lat and v, both inputs).
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


def apply_lag(yr_ss, dt, tau):
    n = len(yr_ss)
    y = np.empty(n)
    y[0] = yr_ss[0]
    for k in range(n - 1):
        a = dt[k] / tau
        y[k + 1] = y[k] + a * (yr_ss[k] - y[k])
    return y


def estimate_delta_offset(delta, v, a_lat):
    """Estimate per-segment steering offset from a_lat / v ~ 0 'going straight' rows.

    On samples where the vehicle is genuinely going straight, a_lat is ~0 and the
    measured delta reveals the (steering_centre - geometric_zero) offset.
    """
    # Going-straight = small lateral accel and reasonable speed.
    mask = (np.abs(a_lat) < 0.3) & (v > 5.0)
    if mask.sum() < 100:
        return 0.0
    # Median is robust to outliers.
    off = float(np.median(delta[mask]))
    # Cap to physical range.
    off = max(-0.02, min(0.02, off))
    return off


def model_yr(delta, v, p, dt):
    g_eff = p["g0"] + p["g2"] * delta * delta
    K_eff = p["K0"] + p["K1"] * v
    yr_ss = v * (g_eff * delta + p["delta0"]) / (p["L"] + K_eff * v * v)
    return apply_lag(yr_ss, dt, p["tau"])


# Refit params *after* applying the offset correction in training.
def platform_of(p):
    return Path(p).resolve().parents[3].name


train_by_plat = {}
for p in train:
    pl = platform_of(p)
    train_by_plat.setdefault(pl, []).append(p)


def fit_platform_v5(paths, L):
    segs = []
    for p in paths:
        df = pd.read_csv(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        if "a_lat_meas_mps2" not in df.columns:
            continue
        t = df["t_s"].to_numpy(float)
        v = df["v_mps"].to_numpy(float)
        delta = df["delta_road_rad"].to_numpy(float)
        a_lat = df["a_lat_meas_mps2"].to_numpy(float)
        yr = df["yaw_rate_meas_rads"].to_numpy(float)
        if len(t) < 5 or np.any(np.diff(t) <= 0):
            continue
        dt = np.diff(t)
        # Per-segment offset
        off = estimate_delta_offset(delta, v, a_lat)
        delta_c = delta - off
        mask = v > 2.0
        if not mask.any():
            continue
        segs.append((delta_c, v, yr, dt, mask))

    def objective(params):
        g0, g2, delta0, K0, K1, tau = params
        if tau <= 0 or K0 < -1e-3:
            return 1e9
        total_sq = 0.0
        n = 0
        for delta, v, yr, dt, mask in segs:
            p = dict(g0=g0, g2=g2, delta0=delta0, K0=K0, K1=K1, tau=tau, L=L)
            y = model_yr(delta, v, p, dt)
            r = y[mask] - yr[mask]
            total_sq += float(np.sum(r * r))
            n += int(mask.sum())
        return total_sq / max(n, 1)

    init = [1.0, 0.0, 0.0, 0.003, 0.0, 0.06]
    res = minimize(objective, x0=init, method="Nelder-Mead",
                   options={"xatol": 1e-6, "fatol": 1e-11, "maxiter": 2000, "disp": False})
    return res.x, res.fun


fitted = {}
for plat, paths in train_by_plat.items():
    L = L_BY_PLATFORM[plat]
    params, fun = fit_platform_v5(paths, L)
    g0, g2, d0, K0, K1, tau = params
    print(f"[{plat}] g0={g0:.4f} g2={g2:.4f} delta0={d0:.5f} K0={K0:.5f} K1={K1:.6f} tau={tau:.4f}  obj={fun:.6e}")
    fitted[plat] = dict(g0=g0, g2=g2, delta0=d0, K0=K0, K1=K1, tau=tau, L=L)

with open(ROOT / "work" / "fitted_v5.json", "w") as fh:
    json.dump(fitted, fh, indent=2)


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
    if "a_lat_meas_mps2" in sim_df.columns:
        a_lat = sim_df["a_lat_meas_mps2"].to_numpy(float)
        off = estimate_delta_offset(delta, v, a_lat)
    else:
        off = 0.0
    delta_c = delta - off
    y = model_yr(delta_c, v, p, dt)
    out["yaw_rate_pred_rads"] = y
    return out


print("\n=== V5 on DEV ===")
res = score(predict, segment_paths=dev)
print(f"yaw_rate_rmse: {res['yaw_rate_rmse']:.6f}")
print(f"cte_rmse:      {res['cte_rmse']:.4f}")
print(f"per_platform:  {res['per_platform']}")
print(f"per_regime:    {res['per_regime']}")

print("\n=== V5 on TRAIN ===")
res = score(predict, segment_paths=train)
print(f"yaw_rate_rmse: {res['yaw_rate_rmse']:.6f}")
print(f"cte_rmse:      {res['cte_rmse']:.4f}")
print(f"per_platform:  {res['per_platform']}")
