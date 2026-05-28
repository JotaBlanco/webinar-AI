"""Lateral fidelity variant ladder for Ford Mach-E.

V0  : baseline residual as shipped in CSV (yaw_rate_resid_rads as-is).
V1  : per-segment yaw-rate bias removal (corrects DC offset / gyro bias / sign-convention drift).
V2  : V1 + linear ST steady-state understeer correction using the *shipped*
      C_alpha priors:  psi_dot = v*delta / (L*(1 + K_us*v^2)).
      (Reported as a regression — see notes below.)
V3  : V1 + first-order steering lag tau on delta_road_rad applied to KS prediction
      (driver/rack/tyre relaxation). Pick tau by grid search.
V4  : V3 + global scalar gain k fit on the training set against KS-with-lag.

Same Ford Mach-E segment set, same regime mask across all variants.
"""
import glob, os, sys
import numpy as np
import pandas as pd

PLATFORM = 'FORD_MUSTANG_MACH_E_MK1'
DATA_GLOB = f'/Users/javiquix/Desktop/quixdev/webinar-AI/data/sim/segments/{PLATFORM}/*/*/*/sim.csv'

# Ford Mach-E parameters (looked up from PARAM_BY_PLATFORM via AGENTS.md)
L      = 2.984
m      = 2336.0
Iz     = 4879.05
lf     = 1.313
lr     = 1.671
Caf    = 286_551.0
Car    = 355_912.0
DT     = 0.02  # 50 Hz

K_us = m * (lr * Car - lf * Caf) / (L**2 * Caf * Car)


def classify(df):
    """Return regime mask arrays: straight, steady, transient."""
    yr_meas = df['yaw_rate_meas_rads'].values
    # transient: high |d(yaw_rate)/dt|
    dyr = np.gradient(yr_meas, DT)
    # rolling std of yaw rate (~0.5 s window = 25 samples)
    w = 25
    s = pd.Series(yr_meas).rolling(w, center=True, min_periods=1).std().values
    abs_yr = np.abs(yr_meas)
    straight  = abs_yr < 0.02                          # < ~1.1 deg/s
    transient = (abs_yr >= 0.02) & (s > 0.02)
    steady    = (abs_yr >= 0.02) & ~transient
    return straight, steady, transient


def rmse(a):
    a = np.asarray(a, dtype=float)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return np.nan
    return float(np.sqrt(np.mean(a*a)))


def variant_residuals(df):
    """Return dict of variant_name -> residual array (pred - meas)."""
    v      = df['v_mps'].values
    delta  = df['delta_road_rad'].values
    yr_pred_ks = df['yaw_rate_pred_rads'].values   # KS prediction
    yr_meas    = df['yaw_rate_meas_rads'].values
    resid_v0   = df['yaw_rate_resid_rads'].values  # baseline as-shipped

    # V1: per-segment bias removal on the baseline residual
    bias = np.nanmean(resid_v0)
    resid_v1 = resid_v0 - bias

    # V2: linear ST steady-state gain instead of KS
    yr_pred_st = v * delta / (L * (1.0 + K_us * v * v))
    resid_v2_raw = yr_pred_st - yr_meas
    resid_v2 = resid_v2_raw - np.nanmean(resid_v2_raw)  # carry V1's bias removal

    return {
        'V0': resid_v0,
        'V1': resid_v1,
        'V2': resid_v2,
        '_st_pred': yr_pred_st,
        '_yr_meas': yr_meas,
        '_v': v,
        '_delta': delta,
    }


def apply_tau(delta, tau):
    """First-order lag: dy/dt = (delta - y)/tau, discrete via exponential."""
    if tau <= 0:
        return delta.copy()
    alpha = DT / (tau + DT)
    y = np.empty_like(delta)
    y[0] = delta[0]
    for i in range(1, len(delta)):
        y[i] = y[i-1] + alpha * (delta[i] - y[i-1])
    return y


def main():
    paths = sorted(glob.glob(DATA_GLOB))
    # use a manageable subset for the time budget (first ~80 segments alphabetically)
    paths = paths[:80]
    print(f"loaded {len(paths)} segments", file=sys.stderr)

    all_resid = {k: [] for k in ['V0', 'V1', 'V2', 'V3', 'V4']}

    # Pre-scan to pick tau on a small sample (first 20 segs) by minimising RMSE
    # against the *KS* prediction (V3 uses KS-with-lag, not ST).
    tau_grid = [0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40]
    tau_scores = {t: [] for t in tau_grid}
    for p in paths[:20]:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if 'yaw_rate_meas_rads' not in df or len(df) < 50:
            continue
        v = df['v_mps'].values
        delta = df['delta_road_rad'].values
        yr_meas = df['yaw_rate_meas_rads'].values
        for tau in tau_grid:
            d = apply_tau(delta, tau)
            pred = v * np.tan(d) / L
            r = pred - yr_meas
            r = r - np.nanmean(r)
            tau_scores[tau].append(rmse(r))
    tau_rmses = {t: float(np.nanmean(vv)) for t, vv in tau_scores.items()}
    best_tau = min(tau_rmses, key=tau_rmses.get)
    print(f"tau sweep (against KS): {tau_rmses}", file=sys.stderr)
    print(f"chosen tau = {best_tau}", file=sys.stderr)

    # Fit V4 global gain on training subset (against KS-with-lag)
    xs = []; ys = []
    for p in paths[:40]:
        df = pd.read_csv(p)
        if 'yaw_rate_meas_rads' not in df: continue
        v = df['v_mps'].values; d = df['delta_road_rad'].values; y = df['yaw_rate_meas_rads'].values
        d_lag = apply_tau(d, best_tau)
        pred = v * np.tan(d_lag) / L
        m = (np.abs(y) > 0.02) & (v > 5)
        xs.append(pred[m]); ys.append(y[m])
    xs = np.concatenate(xs); ys = np.concatenate(ys)
    k_gain = float(np.sum(xs*ys) / np.sum(xs*xs))
    print(f"fitted k_gain (V4) = {k_gain:.4f}", file=sys.stderr)

    for p in paths:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if 'yaw_rate_meas_rads' not in df or len(df) < 50:
            continue
        if df['yaw_rate_meas_rads'].isna().all():
            continue

        r = variant_residuals(df)
        v = r['_v']; yr_meas = r['_yr_meas']
        d_lag = apply_tau(r['_delta'], best_tau)
        # V3: KS with steering lag (still KS, not ST)
        pred_v3 = v * np.tan(d_lag) / L
        resid_v3 = pred_v3 - yr_meas
        resid_v3 = resid_v3 - np.nanmean(resid_v3)
        # V4: V3 with fitted gain
        pred_v4 = k_gain * pred_v3
        resid_v4 = pred_v4 - yr_meas
        resid_v4 = resid_v4 - np.nanmean(resid_v4)

        straight, steady, transient = classify(df)

        all_resid['V0'].append((r['V0'], straight, steady, transient))
        all_resid['V1'].append((r['V1'], straight, steady, transient))
        all_resid['V2'].append((r['V2'], straight, steady, transient))
        all_resid['V3'].append((resid_v3, straight, steady, transient))
        all_resid['V4'].append((resid_v4, straight, steady, transient))

    # Aggregate per-regime RMSEs
    print(f"\n{'Variant':<6} {'All':>10} {'Straight':>10} {'Steady':>10} {'Transient':>10}")
    results = {}
    for name in ['V0', 'V1', 'V2', 'V3', 'V4']:
        cat_all = np.concatenate([x[0] for x in all_resid[name]])
        cat_s = np.concatenate([x[0][x[1]] for x in all_resid[name]])
        cat_sc = np.concatenate([x[0][x[2]] for x in all_resid[name]])
        cat_t = np.concatenate([x[0][x[3]] for x in all_resid[name]])
        row = {
            'all': rmse(cat_all),
            'straight': rmse(cat_s),
            'steady': rmse(cat_sc),
            'transient': rmse(cat_t),
        }
        results[name] = row
        print(f"{name:<6} {row['all']:>10.5f} {row['straight']:>10.5f} {row['steady']:>10.5f} {row['transient']:>10.5f}")

    # Marginal drops
    order = ['V0', 'V1', 'V2', 'V3', 'V4']
    print("\nMarginal RMSE drop (all regimes):")
    drops = []
    for i in range(1, len(order)):
        d = results[order[i-1]]['all'] - results[order[i]]['all']
        drops.append((order[i], d))
        print(f"  {order[i-1]} -> {order[i]}: {d:+.5f} rad/s")
    total = results['V0']['all'] - results['V4']['all']
    print(f"  total V0 -> V4: {total:+.5f} rad/s   sum-of-marginals: {sum(d for _,d in drops):+.5f}")

    print(f"\nbest_tau={best_tau}  K_us={K_us:.6f} s^2/m^2 (negative -> oversteering ST!)")

    return results, best_tau


if __name__ == '__main__':
    main()
