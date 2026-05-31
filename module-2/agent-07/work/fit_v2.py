"""Try richer models:
- (a) Per-platform affine: yr_corr = a * yr_pred + b
- (b) Per-platform with v-dependent gain: yr_corr = yr_pred * g(v)
- (c) Kinematic recompute with steering-ratio correction + understeer: yr = v*delta_eff / (L + K_us*v^2)
  with delta_eff = delta_road * c_s + c_b  (correction for ratio mismatch / bias).
- All with low-pass tau.

This is the classic bicycle steady-state form with understeer gradient K_us [rad/(m/s^2)].
Equivalent form: yr = (v * delta / L) / (1 + K_us * v^2 / L * ... ) but standard:
  yr = v * delta / (L + K_us * v^2)   where K_us has units s^2/m (per CommonRoad steady-state).
"""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-07")
sys.path.insert(0, str(ROOT / "skills" / "load-segments"))

import os
os.chdir(ROOT)

import numpy as np
import pandas as pd
from load import load


L_PLATFORM = {"FORD_MUSTANG_MACH_E_MK1": 2.984, "FORD_F_150_LIGHTNING_MK1": 3.70}


def lowpass_vec(arr, dt, tau):
    if tau <= 0:
        return arr.copy()
    alpha = dt / (tau + dt)
    out = np.empty_like(arr)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = out[i-1] * (1 - alpha) + arr[i] * alpha
    return out


def fit_affine_yr_per_segment(yrp, yrm, mask):
    """Find a, b minimizing sum (a*yrp + b - yrm)^2 over mask."""
    x = yrp[mask]
    y = yrm[mask]
    if len(x) < 5:
        return 1.0, 0.0
    A = np.vstack([x, np.ones_like(x)]).T
    sol, *_ = np.linalg.lstsq(A, y, rcond=None)
    return float(sol[0]), float(sol[1])


def fit_understeer_steering(delta, v, yrm, mask, L):
    """Fit (c_s, K_us) minimising sum (v * c_s * delta / (L + K_us * v^2) - yrm)^2 in least-squares.
    Use nonlinear least squares via scipy if available, else grid.
    """
    from scipy.optimize import least_squares
    d = delta[mask]
    vv = v[mask]
    ym = yrm[mask]
    def resid(p):
        c_s, K_us = p
        denom = L + K_us * vv * vv
        return vv * c_s * d / denom - ym
    x0 = [1.0, 0.0015]
    try:
        out = least_squares(resid, x0, bounds=([0.5, -0.005], [1.5, 0.02]))
        return float(out.x[0]), float(out.x[1])
    except Exception:
        return 1.0, 0.0015


def evaluate(predict_fn, dfs, label):
    sse = 0.0
    n = 0
    for df in dfs:
        v = df["v_mps"].to_numpy()
        yrp = df["yaw_rate_pred_rads"].to_numpy()
        yrm = df["yaw_rate_meas_rads"].to_numpy()
        t = df["t_s"].to_numpy()
        delta = df["delta_road_rad"].to_numpy()
        if len(t) < 2:
            continue
        platform = df.attrs.get("platform", "")
        yrc = predict_fn(t, v, delta, yrp, platform)
        mask = v > 2.0
        sse += float(np.sum((yrc[mask] - yrm[mask])**2))
        n += int(mask.sum())
    print(f"  {label}: rmse={np.sqrt(sse/n):.6f}, n={n}")
    return np.sqrt(sse/n)


# Fit globally over train and check on dev
PARAMS = {}

for platform in ("FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"):
    print(f"\n=== {platform} ===")
    dfs = load(platform=platform)
    n_train = int(len(dfs) * 0.7)
    dfs_train = dfs[:n_train]
    dfs_dev = dfs[n_train:]

    # Pool train data
    all_v, all_d, all_yrp, all_yrm = [], [], [], []
    for df in dfs_train:
        all_v.append(df["v_mps"].to_numpy())
        all_d.append(df["delta_road_rad"].to_numpy())
        all_yrp.append(df["yaw_rate_pred_rads"].to_numpy())
        all_yrm.append(df["yaw_rate_meas_rads"].to_numpy())
    v_all = np.concatenate(all_v)
    d_all = np.concatenate(all_d)
    yrp_all = np.concatenate(all_yrp)
    yrm_all = np.concatenate(all_yrm)
    mask_all = v_all > 2.0

    L = L_PLATFORM[platform]
    # (c) Recompute from delta+v, fit steering scale and understeer gradient
    c_s, K_us = fit_understeer_steering(d_all, v_all, yrm_all, mask_all, L)
    print(f"  Fit: c_s={c_s:.4f}, K_us={K_us:.6f} s^2/m")

    # Also fit (a) affine on yrp
    a, b = fit_affine_yr_per_segment(yrp_all, yrm_all, mask_all)
    print(f"  Affine: a={a:.4f}, b={b:.6f}")

    # Try tau grid with model (c)
    tau_grid = np.array([0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15])
    best_c = (np.inf, 0.0)
    best_a = (np.inf, 0.0)
    sample = dfs_train[::3]
    for tau in tau_grid:
        # model c
        sse = 0.0; n = 0
        sse_a = 0.0
        for df in sample:
            v = df["v_mps"].to_numpy()
            d = df["delta_road_rad"].to_numpy()
            yrp = df["yaw_rate_pred_rads"].to_numpy()
            yrm = df["yaw_rate_meas_rads"].to_numpy()
            t = df["t_s"].to_numpy()
            if len(t) < 2: continue
            dt = float(np.median(np.diff(t)))
            yrc_c = v * c_s * d / (L + K_us * v * v)
            yrc_c = lowpass_vec(yrc_c, dt, tau)
            yrc_a = a * yrp + b
            yrc_a = lowpass_vec(yrc_a, dt, tau)
            mask = v > 2.0
            sse += float(np.sum((yrc_c[mask] - yrm[mask])**2))
            sse_a += float(np.sum((yrc_a[mask] - yrm[mask])**2))
            n += int(mask.sum())
        rmse_c = np.sqrt(sse/n)
        rmse_a = np.sqrt(sse_a/n)
        if rmse_c < best_c[0]: best_c = (rmse_c, tau)
        if rmse_a < best_a[0]: best_a = (rmse_a, tau)
        print(f"    tau={tau:.2f}: rmse_c={rmse_c:.6f}, rmse_a={rmse_a:.6f}")
    print(f"  Best (c): tau={best_c[1]}, rmse={best_c[0]:.6f}")
    print(f"  Best (a): tau={best_a[1]}, rmse={best_a[0]:.6f}")

    PARAMS[platform] = {
        "L": L,
        "c_s": c_s,
        "K_us": K_us,
        "a": a,
        "b": b,
        "tau_c": best_c[1],
        "tau_a": best_a[1],
    }

    # Evaluate on dev
    print("  DEV results:")
    def pred_v0(t, v, d, yrp, plt): return yrp
    def pred_c(t, v, d, yrp, plt):
        dt = float(np.median(np.diff(t))) if len(t) > 1 else 0.02
        yrc = v * c_s * d / (L + K_us * v * v)
        return lowpass_vec(yrc, dt, best_c[1])
    def pred_a(t, v, d, yrp, plt):
        dt = float(np.median(np.diff(t))) if len(t) > 1 else 0.02
        return lowpass_vec(a * yrp + b, dt, best_a[1])
    evaluate(pred_v0, dfs_dev, "V0")
    evaluate(pred_c, dfs_dev, "model-c (recompute)")
    evaluate(pred_a, dfs_dev, "model-a (affine)")

import json
print("\n\nPARAMS:")
print(json.dumps(PARAMS, indent=2))
