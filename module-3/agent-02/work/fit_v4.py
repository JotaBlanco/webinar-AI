"""V4: V3 + per-segment bias correction using straight-driving rows of the
*input data itself* (no truth needed!).

The trick: on rows where |delta| is very small, the model predicts ~yr_ss ~ 0.
If the *measured yaw rate sensor* exists in the input (it does, as the truth channel),
we'd be cheating. So instead: we use the measured a_lat as a 'physically grounded'
alternative estimate of yaw rate (yr = a_lat / v) on slow-steering rows, and adjust
our model output by a small constant to match it on those rows. This is inferable at
inference time because a_lat is an input signal (not the target).

Equivalent intuition: if our model over-predicts yaw on average during gentle driving,
shift it down by a constant.
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


def apply_lag(yr_ss, dt, tau):
    n = len(yr_ss)
    y = np.empty(n)
    y[0] = yr_ss[0]
    for k in range(n - 1):
        a = dt[k] / tau
        y[k + 1] = y[k] + a * (yr_ss[k] - y[k])
    return y


def model_yr(delta, v, p, dt):
    g_eff = p["g0"] + p["g2"] * delta * delta
    K_eff = p["K0"] + p["K1"] * v
    yr_ss = v * (g_eff * delta + p["delta0"]) / (p["L"] + K_eff * v * v)
    return apply_lag(yr_ss, dt, p["tau"])


with open(ROOT / "work" / "fitted_v3.json") as fh:
    fitted = json.load(fh)


def per_segment_bias_correction(yr_model, delta, v, a_lat):
    """Estimate a constant additive bias from a_lat-derived yaw on near-straight rows."""
    # a_lat / v is an alternative yaw rate estimate (kinematic identity).
    # In straight driving both should be ~0. Their offset reveals a bias.
    mask = (np.abs(delta) < 0.005) & (v > 5.0)
    if mask.sum() < 50:
        return 0.0
    vs = np.where(v > 1.0, v, 1.0)
    yr_alat = a_lat / vs
    # Use median for robustness; small outliers (potholes) shouldn't move it.
    bias = float(np.median(yr_model[mask] - yr_alat[mask]))
    # Cap to avoid runaway in pathological segments.
    bias = max(-0.01, min(0.01, bias))
    return bias


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
    y = model_yr(delta, v, p, dt)
    if "a_lat_meas_mps2" in sim_df.columns:
        a_lat = sim_df["a_lat_meas_mps2"].to_numpy(float)
        bias = per_segment_bias_correction(y, delta, v, a_lat)
        y = y - bias
    out["yaw_rate_pred_rads"] = y
    return out


print("=== V4 on DEV ===")
res = score(predict, segment_paths=dev)
print(f"yaw_rate_rmse: {res['yaw_rate_rmse']:.6f}")
print(f"cte_rmse:      {res['cte_rmse']:.4f}")
print(f"per_platform:  {res['per_platform']}")
print(f"per_regime:    {res['per_regime']}")

print("\n=== V4 on TRAIN ===")
res = score(predict, segment_paths=train)
print(f"yaw_rate_rmse: {res['yaw_rate_rmse']:.6f}")
print(f"cte_rmse:      {res['cte_rmse']:.4f}")
print(f"per_platform:  {res['per_platform']}")
