"""Final fit: per-platform (c_s, K_us, tau) joint nonlinear LS over full train data.

Predict: yr = lowpass( v * c_s * delta / (L + K_us * v^2), tau).
Lowpass is non-differentiable in scipy LSQ closed-form, so we grid tau and LSQ (c_s, K_us).
"""
import sys, os
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-07")
sys.path.insert(0, str(ROOT / "skills" / "load-segments"))
sys.path.insert(0, str(ROOT / "_shared"))
os.chdir(ROOT)

import numpy as np
import json
from scipy.optimize import least_squares
from load import load

L_PLATFORM = {"FORD_MUSTANG_MACH_E_MK1": 2.984, "FORD_F_150_LIGHTNING_MK1": 3.70}


def lowpass(arr, dt, tau):
    if tau <= 0:
        return arr.copy()
    alpha = dt / (tau + dt)
    out = np.empty_like(arr)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = out[i-1] * (1 - alpha) + arr[i] * alpha
    return out


def fit_for_platform(platform, dfs_train):
    L = L_PLATFORM[platform]
    # Pre-extract per-segment v, delta, yrm, dt
    segs = []
    for df in dfs_train:
        v = df["v_mps"].to_numpy()
        d = df["delta_road_rad"].to_numpy()
        yrm = df["yaw_rate_meas_rads"].to_numpy()
        t = df["t_s"].to_numpy()
        if len(t) < 5:
            continue
        dt = float(np.median(np.diff(t)))
        mask = v > 2.0
        if mask.sum() < 50:
            continue
        segs.append((v, d, yrm, dt, mask))
    print(f"  {len(segs)} usable segments for fit")

    best = None
    tau_grid = np.arange(0.0, 0.21, 0.02)
    for tau in tau_grid:
        # For a fixed tau, residual function in (c_s, K_us).
        def resid(p):
            c_s, K_us = p
            chunks = []
            for v, d, yrm, dt, mask in segs:
                yr = v * c_s * d / (L + K_us * v * v)
                yr = lowpass(yr, dt, tau)
                chunks.append(yr[mask] - yrm[mask])
            return np.concatenate(chunks)
        try:
            out = least_squares(resid, [1.0, 0.002], bounds=([0.3, -0.005], [2.0, 0.02]))
            r = out.fun
            rmse = np.sqrt((r*r).mean())
            if best is None or rmse < best[0]:
                best = (rmse, tau, float(out.x[0]), float(out.x[1]))
            print(f"    tau={tau:.2f}: c_s={out.x[0]:.4f}, K_us={out.x[1]:.5f}, rmse={rmse:.6f}")
        except Exception as e:
            print(f"    tau={tau:.2f}: fit failed: {e}")
    return best  # (rmse, tau, c_s, K_us)


RESULTS = {}
for platform in ("FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"):
    print(f"\n=== {platform} ===")
    dfs = load(platform=platform)
    n_train = int(len(dfs) * 0.7)
    dfs_train = dfs[:n_train]
    dfs_dev = dfs[n_train:]
    best = fit_for_platform(platform, dfs_train)
    print(f"  BEST: tau={best[1]:.2f}, c_s={best[2]:.4f}, K_us={best[3]:.5f}, train-rmse={best[0]:.6f}")
    RESULTS[platform] = {"L": L_PLATFORM[platform], "c_s": best[2], "K_us": best[3], "tau": best[1]}

    # Evaluate on dev
    c_s, K_us, tau = best[2], best[3], best[1]
    L = L_PLATFORM[platform]
    sse = 0.0; n = 0
    for df in dfs_dev:
        v = df["v_mps"].to_numpy()
        d = df["delta_road_rad"].to_numpy()
        yrm = df["yaw_rate_meas_rads"].to_numpy()
        t = df["t_s"].to_numpy()
        if len(t) < 2: continue
        dt = float(np.median(np.diff(t)))
        yr = v * c_s * d / (L + K_us * v * v)
        yr = lowpass(yr, dt, tau)
        mask = v > 2.0
        sse += float(np.sum((yr[mask] - yrm[mask])**2))
        n += int(mask.sum())
    print(f"  DEV rmse: {np.sqrt(sse/n):.6f}")

print("\nFinal params:")
print(json.dumps(RESULTS, indent=2))
with open(ROOT / "work" / "params_v3.json", "w") as f:
    json.dump(RESULTS, f, indent=2)
