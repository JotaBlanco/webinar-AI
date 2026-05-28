"""Lateral-fidelity variant ladder for Ford Mach-E MK1.

V0: KS baseline (yaw_rate_pred_rads already in CSV)
V1: KS + per-segment yaw-rate bias (soaks IMU gyro offset on straights)
V2: Linear ST steady-state gain, prior C_α
V3: Linear ST, fit C_α (LOSO-bounded), per-segment bias retained
V4: Ridge residual learner on [v, |a_y|, |delta|, sign(ddelta/dt)], LOSO

Same segment set, same regime mask, every rung.
"""
from __future__ import annotations
import glob, os, sys, json
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from sklearn.linear_model import Ridge

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-3/agent-03"
SIM_GLOB = f"{ROOT}/data/sim/segments/{PLATFORM}/*/*/*/sim.csv"

# Mach-E params
L = 2.984
m = 2336.0
I_z = 4879.05
l_f = 1.313
l_r = 1.671
C_af_prior = 286_551.0
C_ar_prior = 355_912.0

V_MIN = 2.0  # below this, fall back to KS

def load_segments(max_n=None):
    paths = sorted(glob.glob(SIM_GLOB))
    if max_n:
        paths = paths[:max_n]
    segs = []
    for p in paths:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        if df["yaw_rate_meas_rads"].isna().all():
            continue
        df = df.dropna(subset=["yaw_rate_meas_rads", "yaw_rate_pred_rads",
                               "delta_road_rad", "v_mps"])
        if len(df) < 50:
            continue
        sid = "/".join(p.split("/")[-4:-1])
        df = df.copy()
        df["__seg"] = sid
        segs.append(df)
    return segs

def ks_pred(df):
    # already in CSV; recompute for sanity: (v/L)*tan(delta)
    return (df["v_mps"].values / L) * np.tan(df["delta_road_rad"].values)

def st_pred(df, C_af, C_ar):
    v = df["v_mps"].values
    d = df["delta_road_rad"].values
    K_us = m * (l_r * C_ar - l_f * C_af) / (L**2 * C_af * C_ar)
    psi_dot = v * d / (L * (1.0 + K_us * v * v))
    # low-speed fallback to KS
    mask_low = v < V_MIN
    psi_dot[mask_low] = (v[mask_low] / L) * np.tan(d[mask_low])
    return psi_dot

def regime_mask(df):
    d = df["delta_road_rad"].values
    dd = np.gradient(d, 0.02)
    straight = np.abs(d) < 0.01
    steady = (np.abs(d) >= 0.01) & (np.abs(dd) < 0.05)
    transient = (np.abs(d) >= 0.01) & (np.abs(dd) >= 0.05)
    return straight, steady, transient

def rmse(a):
    a = np.asarray(a, dtype=float)
    a = a[np.isfinite(a)]
    return float(np.sqrt(np.mean(a*a))) if len(a) else float("nan")

def per_regime_rmse(resid, masks):
    s, st, tr = masks
    return {
        "all": rmse(resid),
        "straight": rmse(resid[s]),
        "steady": rmse(resid[st]),
        "transient": rmse(resid[tr]),
    }

def main(max_n=80):
    segs = load_segments(max_n=max_n)
    print(f"# Loaded {len(segs)} Mach-E segments", file=sys.stderr)
    if not segs:
        print("no segments", file=sys.stderr); return

    all_df = pd.concat(segs, ignore_index=True)
    y_meas = all_df["yaw_rate_meas_rads"].values

    # Sign sanity check
    cm = all_df[all_df["delta_road_rad"].abs() > 0.01]
    corr_sign = np.corrcoef(cm["delta_road_rad"], cm["yaw_rate_meas_rads"])[0,1]
    print(f"# sign-sanity corr(delta_road, yaw_rate_meas) on cornering = {corr_sign:.3f}", file=sys.stderr)

    masks = regime_mask(all_df)

    results = {}

    # V0: KS as-is
    y_v0 = all_df["yaw_rate_pred_rads"].values
    r_v0 = y_v0 - y_meas
    results["V0_KS"] = per_regime_rmse(r_v0, masks)

    # V1: KS + per-segment bias (estimated on straights only to avoid leakage)
    bias = {}
    d = all_df["delta_road_rad"].values
    straight_mask = np.abs(d) < 0.01
    for sid, g_idx in all_df.groupby("__seg").indices.items():
        idx = np.array(g_idx)
        st_idx = idx[straight_mask[idx]]
        if len(st_idx) >= 20:
            bias[sid] = float(np.mean(r_v0[st_idx]))
        else:
            bias[sid] = 0.0
    bvec = all_df["__seg"].map(bias).values
    y_v1 = y_v0 - bvec
    r_v1 = y_v1 - y_meas
    results["V1_KS+bias"] = per_regime_rmse(r_v1, masks)

    # V2: Linear ST with prior C_alpha + per-segment bias
    y_v2_raw = st_pred(all_df, C_af_prior, C_ar_prior)
    r_v2_raw = y_v2_raw - y_meas
    bias2 = {}
    for sid, g_idx in all_df.groupby("__seg").indices.items():
        idx = np.array(g_idx)
        st_idx = idx[straight_mask[idx]]
        if len(st_idx) >= 20:
            bias2[sid] = float(np.mean(r_v2_raw[st_idx]))
        else:
            bias2[sid] = 0.0
    bvec2 = all_df["__seg"].map(bias2).values
    y_v2 = y_v2_raw - bvec2
    r_v2 = y_v2 - y_meas
    results["V2_ST_prior+bias"] = per_regime_rmse(r_v2, masks)

    # V3: Fit C_alpha by minimising RMSE on cornering samples, bounded
    cornering = (np.abs(d) >= 0.01) & (all_df["v_mps"].values > V_MIN)
    v_c = all_df["v_mps"].values[cornering]
    d_c = d[cornering]
    y_c = y_meas[cornering]
    seg_c = all_df["__seg"].values[cornering]

    def loss(scale):
        Caf = C_af_prior * scale
        Car = C_ar_prior * scale
        K_us = m * (l_r * Car - l_f * Caf) / (L**2 * Caf * Car)
        pred = v_c * d_c / (L * (1.0 + K_us * v_c * v_c))
        return rmse(pred - y_c)

    res = minimize_scalar(loss, bounds=(0.2, 2.0), method="bounded")
    scale_fit = float(res.x)
    Caf_fit = C_af_prior * scale_fit
    Car_fit = C_ar_prior * scale_fit
    pegged = scale_fit <= 0.21 or scale_fit >= 1.99
    y_v3_raw = st_pred(all_df, Caf_fit, Car_fit)
    r_v3_raw = y_v3_raw - y_meas
    bias3 = {}
    for sid, g_idx in all_df.groupby("__seg").indices.items():
        idx = np.array(g_idx)
        st_idx = idx[straight_mask[idx]]
        if len(st_idx) >= 20:
            bias3[sid] = float(np.mean(r_v3_raw[st_idx]))
        else:
            bias3[sid] = 0.0
    bvec3 = all_df["__seg"].map(bias3).values
    y_v3 = y_v3_raw - bvec3
    r_v3 = y_v3 - y_meas
    results["V3_ST_fit+bias"] = per_regime_rmse(r_v3, masks)

    # V4: Ridge residual learner on V3 residuals, LOSO
    v = all_df["v_mps"].values
    a_y_pred = all_df["a_y_pred_mps2"].values if "a_y_pred_mps2" in all_df else np.zeros_like(v)
    ddel = np.gradient(d, 0.02)
    X = np.column_stack([v, np.abs(a_y_pred), np.abs(d), np.sign(ddel)])
    y_resid = r_v3  # learn correction to V3 residuals
    segs_arr = all_df["__seg"].values
    unique = np.unique(segs_arr)
    correction = np.zeros_like(y_resid)
    for held in unique:
        train = segs_arr != held
        test = ~train
        if train.sum() < 50 or test.sum() < 1:
            continue
        mdl = Ridge(alpha=1.0)
        mdl.fit(X[train], y_resid[train])
        correction[test] = mdl.predict(X[test])
    y_v4 = y_v3 - correction
    r_v4 = y_v4 - y_meas
    results["V4_ST_fit+bias+ridgeLOSO"] = per_regime_rmse(r_v4, masks)

    # Print
    print(json.dumps({
        "platform": PLATFORM,
        "n_segments": int(len(np.unique(all_df["__seg"]))),
        "n_samples": int(len(all_df)),
        "sign_check_corr": float(corr_sign),
        "regime_counts": {
            "straight": int(masks[0].sum()),
            "steady": int(masks[1].sum()),
            "transient": int(masks[2].sum()),
        },
        "Caf_fit": Caf_fit,
        "Car_fit": Car_fit,
        "scale_fit": scale_fit,
        "scale_pegged": pegged,
        "results": results,
    }, indent=2))

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 80
    main(max_n=n)
