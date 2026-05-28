"""Lateral fidelity variant ladder on FORD_MUSTANG_MACH_E_MK1 sim CSVs.

V0: baseline yaw_rate_resid_rads RMSE as-is.
V1: remove per-segment yaw-rate bias (sensor zero offset).
V2: replace KS yaw-rate gain (v/L)*tan(delta) with linear single-track
    steady-state gain v*delta / (L*(1+K_us*v^2)) using PARAM_BY_PLATFORM.
V3: first-order lag on delta_road_rad (rack/EPS dynamics), tau fit globally
    by minimising overall RMSE.
V4: global steering-offset calibration (mean delta_road_rad bias).

Attribution: marginal (cumulative). Sum of marginal drops V0->V_last reported
against the total drop.
"""
from __future__ import annotations
import sys, glob, os, math, json
import numpy as np
import pandas as pd

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-2/agent-03"
SIM_GLOB = f"{ROOT}/data/sim/segments/{PLATFORM}/*/*/*/sim.csv"

# From parameters.py (also stated in AGENTS.md - openpilot canonical values)
PARAMS = {
    "FORD_MUSTANG_MACH_E_MK1": dict(
        L=2.984, m=2336.0, I_z=4879.05, l_f=1.313, l_r=1.671,
        C_alpha_f=286551.0, C_alpha_r=355912.0, i_s=17.0
    ),
}
P = PARAMS[PLATFORM]
L = P["L"]; m = P["m"]; l_f = P["l_f"]; l_r = P["l_r"]
Cf = P["C_alpha_f"]; Cr = P["C_alpha_r"]
K_us = m * (l_r * Cr - l_f * Cf) / (L**2 * Cf * Cr)


def load_all(limit=None):
    files = sorted(glob.glob(SIM_GLOB))
    if limit:
        files = files[:limit]
    dfs = []
    for i, fp in enumerate(files):
        try:
            df = pd.read_csv(fp)
        except Exception:
            continue
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        df = df.dropna(subset=["yaw_rate_meas_rads", "yaw_rate_pred_rads",
                                "delta_road_rad", "v_mps"])
        if len(df) < 100:
            continue
        df["seg_id"] = i
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True), files


def regime_mask(df):
    """Three exclusive regimes by |yaw_rate_meas| and its derivative."""
    yr = df["yaw_rate_meas_rads"].values
    dt = 0.02
    dyr = np.gradient(yr, dt)
    abs_yr = np.abs(yr)
    abs_dyr = np.abs(dyr)
    # straight: |yr| < 0.02 rad/s
    straight = abs_yr < 0.02
    # transient: derivative high OR moderately high
    transient = (~straight) & (abs_dyr > 0.15)
    steady = (~straight) & (~transient)
    return {"straight": straight, "steady_corner": steady, "transient_corner": transient}


def rmse(x):
    return float(np.sqrt(np.mean(np.square(x))))


def regime_rmse(resid, regimes):
    out = {"overall": rmse(resid)}
    for name, mask in regimes.items():
        out[name] = rmse(resid[mask]) if mask.any() else float("nan")
    return out


def v0_resid(df):
    return df["yaw_rate_resid_rads"].values  # pred - meas, KS as-is


def v1_resid(df):
    """Remove per-segment mean residual (bias)."""
    r = df["yaw_rate_resid_rads"].values.copy()
    for sid, idx in df.groupby("seg_id").indices.items():
        r[idx] = r[idx] - r[idx].mean()
    return r


def st_yawrate(v, delta):
    """Linear single-track steady-state yaw-rate gain."""
    return v * delta / (L * (1.0 + K_us * v * v))


def v2_resid(df, bias_corrected=True):
    """Use ST steady-state gain instead of KS gain.

    If bias_corrected, also apply V1's per-segment bias removal so V2 is the
    *marginal* effect of upgrading the gain.
    """
    v = df["v_mps"].values
    d = df["delta_road_rad"].values
    pred_st = st_yawrate(v, d)
    meas = df["yaw_rate_meas_rads"].values
    r = pred_st - meas
    if bias_corrected:
        for sid, idx in df.groupby("seg_id").indices.items():
            r[idx] = r[idx] - r[idx].mean()
    return r


def lag_delta(df, tau):
    """First-order lag on delta_road_rad, per segment."""
    dt = 0.02
    out = np.empty(len(df))
    alpha = dt / (tau + dt) if tau > 0 else 1.0
    for sid, idx in df.groupby("seg_id").indices.items():
        d = df["delta_road_rad"].values[idx]
        y = np.empty_like(d)
        y[0] = d[0]
        for i in range(1, len(d)):
            y[i] = y[i - 1] + alpha * (d[i] - y[i - 1])
        out[idx] = y
    return out


def v3_resid(df, tau):
    v = df["v_mps"].values
    d_lag = lag_delta(df, tau)
    pred = st_yawrate(v, d_lag)
    meas = df["yaw_rate_meas_rads"].values
    r = pred - meas
    for sid, idx in df.groupby("seg_id").indices.items():
        r[idx] = r[idx] - r[idx].mean()
    return r


def v4_resid(df, tau, delta_off):
    v = df["v_mps"].values
    d_lag = lag_delta(df, tau) - delta_off
    pred = st_yawrate(v, d_lag)
    meas = df["yaw_rate_meas_rads"].values
    r = pred - meas
    for sid, idx in df.groupby("seg_id").indices.items():
        r[idx] = r[idx] - r[idx].mean()
    return r


def main():
    print(f"K_us (Mach-E linear ST) = {K_us:.6f} s^2/m^2")
    df, files = load_all()
    print(f"Loaded {df['seg_id'].nunique()} segments / {len(df)} samples "
          f"({len(df)*0.02/60:.1f} min @50 Hz)")

    regimes = regime_mask(df)
    for name, m_ in regimes.items():
        print(f"  regime {name}: {m_.sum()} samples ({100*m_.mean():.1f}%)")

    results = []

    # V0
    r0 = v0_resid(df)
    res = regime_rmse(r0, regimes)
    res.update(name="V0_baseline_KS",
               desc="yaw_rate_resid_rads as-is (pred - meas), no preprocessing")
    results.append(res)

    # V1 = V0 + per-seg bias removal
    r1 = v1_resid(df)
    res = regime_rmse(r1, regimes)
    res.update(name="V1_seg_bias_removal",
               desc="V0 minus per-segment mean residual (sensor zero / install offset)")
    results.append(res)

    # V2 = V1 + ST steady-state gain
    r2 = v2_resid(df, bias_corrected=True)
    res = regime_rmse(r2, regimes)
    res.update(name="V2_ST_steady_state_gain",
               desc="Replace (v/L)tan(d) with v*d/(L(1+K_us*v^2)); + V1 bias removal")
    results.append(res)

    # V3 = V2 + steering lag tau. Fit tau by grid.
    best_tau = 0.0
    best_rmse = float("inf")
    for tau in [0.02, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.25, 0.30]:
        r = v3_resid(df, tau)
        e = rmse(r)
        if e < best_rmse:
            best_rmse = e
            best_tau = tau
    print(f"V3 best tau = {best_tau:.3f} s  (overall RMSE {best_rmse*1000:.3f} mrad/s)")
    r3 = v3_resid(df, best_tau)
    res = regime_rmse(r3, regimes)
    res.update(name=f"V3_steering_lag_tau={best_tau:.2f}s",
               desc="V2 + 1st-order lag on delta_road (rack/EPS dynamics)")
    results.append(res)

    # V4 = V3 + fit empirical K_us (single scalar) — addresses the suspicion
    # that the shipped Cα prior is wrong for these tyres/roads. Grid search.
    def v4_kus_resid(df, tau, k_us):
        v = df["v_mps"].values
        d_lag = lag_delta(df, tau)
        pred = v * d_lag / (L * (1.0 + k_us * v * v))
        meas = df["yaw_rate_meas_rads"].values
        r = pred - meas
        for sid, idx in df.groupby("seg_id").indices.items():
            r[idx] = r[idx] - r[idx].mean()
        return r

    best_kus = K_us
    best_rmse4 = float("inf")
    for kus in np.linspace(-0.002, 0.012, 29):
        e = rmse(v4_kus_resid(df, best_tau, kus))
        if e < best_rmse4:
            best_rmse4 = e
            best_kus = kus
    print(f"V4 best K_us = {best_kus:.6f} (prior {K_us:.6f}); "
          f"overall RMSE {best_rmse4*1000:.3f} mrad/s")
    r4 = v4_kus_resid(df, best_tau, best_kus)
    res = regime_rmse(r4, regimes)
    res.update(name=f"V4_fit_Kus={best_kus:.5f}",
               desc=f"V3 + empirical understeer gradient (prior K_us={K_us:.5f})")
    results.append(res)

    # Print ladder
    print()
    print(f"{'variant':<40} {'overall':>9} {'straight':>9} {'steady':>9} {'transient':>10}  {'marginal':>9}")
    prev = None
    total = results[0]["overall"]
    marginal_sum = 0.0
    for r in results:
        marg = "" if prev is None else f"{1000*(prev - r['overall']):+.3f}"
        if prev is not None:
            marginal_sum += (prev - r["overall"])
        print(f"{r['name']:<40} {1000*r['overall']:>9.3f} "
              f"{1000*r['straight']:>9.3f} {1000*r['steady_corner']:>9.3f} "
              f"{1000*r['transient_corner']:>10.3f}  {marg:>9}")
        prev = r["overall"]
    total_drop = results[0]["overall"] - results[-1]["overall"]
    print(f"\nTotal drop V0 -> V_last: {1000*total_drop:.3f} mrad/s "
          f"({100*total_drop/results[0]['overall']:.1f}%)")
    print(f"Sum of marginal drops:    {1000*marginal_sum:.3f} mrad/s "
          f"(diff {100*(marginal_sum-total_drop)/total_drop:+.2f}%)")

    # Save JSON for the report
    out_path = f"{ROOT}/out/ladder.json"
    with open(out_path, "w") as f:
        json.dump({"K_us_prior": K_us, "tau": best_tau, "K_us_fit": best_kus,
                   "n_segments": int(df["seg_id"].nunique()),
                   "n_samples": int(len(df)),
                   "regime_counts": {k: int(v.sum()) for k, v in regimes.items()},
                   "results": results}, f, indent=2)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
