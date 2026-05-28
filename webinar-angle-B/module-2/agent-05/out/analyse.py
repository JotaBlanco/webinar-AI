"""Lateral fidelity variant ladder on Ford Mach-E.

V0: baseline yaw_rate_resid_rads as-is.
V1: V0 + per-segment bias removal (constant offset, e.g. gyro/steering misalignment).
V2: V1 + steady-state understeer gradient correction (linear in v^2*delta) — closes
    the gap that an ST upgrade would address, while staying interpretable.
V3: V2 + first-order steering actuator lag (tau) applied to delta before yaw-rate
    recompute — captures the transient response.

All variants share the same segment set and the same regime mask. Marginal
attribution is forward-incremental: each row's drop is RMSE(V_{i-1}) - RMSE(V_i).
"""
import glob
import os
import numpy as np
import pandas as pd

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
L = 2.984
DATA_GLOB = f"/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-2/agent-05/data/sim/segments/{PLATFORM}/*/*/*/sim.csv"

files = sorted(glob.glob(DATA_GLOB))
print(f"segments: {len(files)}")

# Regime thresholds
V_MIN = 5.0           # exclude near-standstill
DELTA_STRAIGHT = 0.01 # rad (~0.6 deg road wheel) -> straight
YAW_TRANSIENT_RATE = 0.5  # rad/s/s on dyaw/dt -> transient

def regimes(df):
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    yaw_meas = df["yaw_rate_meas_rads"].to_numpy()
    dt = np.gradient(df["t_s"].to_numpy())
    dyaw = np.gradient(yaw_meas) / np.where(dt > 0, dt, 1e-3)
    move = v > V_MIN
    straight = move & (np.abs(delta) < DELTA_STRAIGHT)
    transient = move & (np.abs(delta) >= DELTA_STRAIGHT) & (np.abs(dyaw) > YAW_TRANSIENT_RATE)
    steady = move & (np.abs(delta) >= DELTA_STRAIGHT) & (np.abs(dyaw) <= YAW_TRANSIENT_RATE)
    return move, straight, steady, transient

# Pre-load and assemble residuals per variant
all_rows = []
for f in files:
    try:
        df = pd.read_csv(f)
    except Exception:
        continue
    needed = {"t_s","v_mps","delta_road_rad","yaw_rate_meas_rads",
              "yaw_rate_pred_rads","yaw_rate_resid_rads"}
    if not needed.issubset(df.columns):
        continue
    if len(df) < 50:
        continue
    move, straight, steady, transient = regimes(df)
    if move.sum() < 50:
        continue

    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    yaw_meas = df["yaw_rate_meas_rads"].to_numpy()
    yaw_pred = df["yaw_rate_pred_rads"].to_numpy()
    resid_v0 = yaw_pred - yaw_meas

    # V1: per-segment bias = mean residual over STRAIGHT samples (sensor zero offset)
    if straight.sum() >= 20:
        bias = np.mean(resid_v0[straight])
    else:
        bias = np.mean(resid_v0[move])
    resid_v1 = resid_v0 - bias

    # V2: understeer-gradient correction. KS gives yaw_pred = (v/L)*tan(delta).
    # ST steady-state yaw = v*delta/(L*(1 + K_us*v^2)). For small K_us*v^2,
    # yaw_pred - yaw_ST ≈ yaw_pred * K_us * v^2. Fit a single K_us per segment
    # on steady cornering samples (least squares) to predict the residual after bias.
    if steady.sum() >= 50:
        x = (yaw_pred * v * v)[steady]
        y = resid_v1[steady]
        # resid ≈ K_us * (yaw_pred * v^2) -> K_us = (x·y) / (x·x)
        denom = np.dot(x, x)
        k_us = float(np.dot(x, y) / denom) if denom > 0 else 0.0
    else:
        k_us = 0.0
    # Clamp k_us to physically plausible range (small positive understeer typical)
    k_us = float(np.clip(k_us, -0.01, 0.02))
    resid_v2 = resid_v1 - k_us * yaw_pred * v * v

    # V3: steering actuator lag. Apply first-order filter to delta with tau,
    # recompute KS yaw with filtered delta, take that as the corrected pred.
    # Estimate tau by minimising transient residual on a small grid.
    dt_arr = np.gradient(df["t_s"].to_numpy())
    dt_med = float(np.median(dt_arr[dt_arr > 0])) if np.any(dt_arr > 0) else 0.02
    best_tau, best_rmse = 0.0, np.inf
    for tau in [0.0, 0.05, 0.10, 0.15, 0.20, 0.30]:
        if tau <= 0:
            delta_f = delta.copy()
        else:
            alpha = dt_med / (tau + dt_med)
            delta_f = np.empty_like(delta)
            delta_f[0] = delta[0]
            for i in range(1, len(delta)):
                delta_f[i] = delta_f[i-1] + alpha * (delta[i] - delta_f[i-1])
        yaw_pred_lag = (v / L) * np.tan(delta_f)
        resid_try = (yaw_pred_lag - yaw_meas) - bias - k_us * yaw_pred_lag * v * v
        if transient.sum() >= 20:
            rmse_t = np.sqrt(np.mean(resid_try[transient] ** 2))
        else:
            rmse_t = np.sqrt(np.mean(resid_try[move] ** 2))
        if rmse_t < best_rmse:
            best_rmse, best_tau = rmse_t, tau
    if best_tau <= 0:
        resid_v3 = resid_v2
    else:
        alpha = dt_med / (best_tau + dt_med)
        delta_f = np.empty_like(delta)
        delta_f[0] = delta[0]
        for i in range(1, len(delta)):
            delta_f[i] = delta_f[i-1] + alpha * (delta[i] - delta_f[i-1])
        yaw_pred_lag = (v / L) * np.tan(delta_f)
        resid_v3 = (yaw_pred_lag - yaw_meas) - bias - k_us * yaw_pred_lag * v * v

    rec = {
        "v0": resid_v0[move],
        "v1": resid_v1[move],
        "v2": resid_v2[move],
        "v3": resid_v3[move],
        "v0_s": resid_v0[straight], "v1_s": resid_v1[straight],
        "v2_s": resid_v2[straight], "v3_s": resid_v3[straight],
        "v0_c": resid_v0[steady],   "v1_c": resid_v1[steady],
        "v2_c": resid_v2[steady],   "v3_c": resid_v3[steady],
        "v0_t": resid_v0[transient],"v1_t": resid_v1[transient],
        "v2_t": resid_v2[transient],"v3_t": resid_v3[transient],
        "bias": bias, "k_us": k_us, "tau": best_tau,
    }
    all_rows.append(rec)

print(f"used segments: {len(all_rows)}")

def cat(key):
    arrs = [r[key] for r in all_rows if len(r[key]) > 0]
    return np.concatenate(arrs) if arrs else np.array([])

def rmse(a):
    return float(np.sqrt(np.mean(a ** 2))) if len(a) else float("nan")

variants = ["v0","v1","v2","v3"]
print("\nRMSE yaw_rate_resid_rads (rad/s):")
print(f"{'variant':<6} {'overall':>10} {'straight':>10} {'steady':>10} {'transient':>10}")
prev_overall = None
marginal = {}
for v in variants:
    o = rmse(cat(v))
    s = rmse(cat(v+"_s"))
    c = rmse(cat(v+"_c"))
    t = rmse(cat(v+"_t"))
    drop = (prev_overall - o) if prev_overall is not None else 0.0
    marginal[v] = drop
    print(f"{v:<6} {o:>10.5f} {s:>10.5f} {c:>10.5f} {t:>10.5f}   marginal_drop={drop:+.5f}")
    prev_overall = o

print("\nmedian fitted parameters:")
print(f"  bias  median = {np.median([r['bias'] for r in all_rows]):+.5f} rad/s")
print(f"  k_us  median = {np.median([r['k_us'] for r in all_rows]):+.5f} s^2/m^2")
print(f"  tau   median = {np.median([r['tau']  for r in all_rows]):+.3f} s")

total_drop = rmse(cat('v0')) - rmse(cat('v3'))
sum_marg = marginal['v1'] + marginal['v2'] + marginal['v3']
print(f"\ntotal V0->V3 drop = {total_drop:+.5f}; sum of marginals = {sum_marg:+.5f}")
