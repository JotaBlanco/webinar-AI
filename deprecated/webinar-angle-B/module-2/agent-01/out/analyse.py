#!/usr/bin/env python3
"""
Lateral-fidelity variant ladder for FORD platforms.

V0: baseline yaw_rate_resid_rads (pred - meas) as-is.
V1: V0 + per-segment yaw-rate bias removal (subtract mean residual).
V2: V1 + steering-to-yaw latency alignment (per-segment time shift,
    estimated by xcorr in the cornering regime; applied to the
    predicted yaw rate by integer-sample shift).
V3: V2 + ST steady-state yaw-rate gain (understeer correction) instead
    of pure KS kinematic gain. Re-predicts yaw rate from delta_road_rad
    and v_mps using:  psi_dot = v*delta/(L*(1+K_us*v^2)).

Regime mask (consistent across all variants):
  straight:   |psi_rate_meas| < 0.05 rad/s and v > 2 m/s
  steady:     |psi_rate_meas| >= 0.05 rad/s and |d/dt psi_rate_meas| < 0.2 rad/s^2
  transient:  |psi_rate_meas| >= 0.05 rad/s and |d/dt psi_rate_meas| >= 0.2 rad/s^2
We drop v<2 m/s samples from all regimes (creep / standstill).
"""
import os, sys, glob, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path('/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-2/agent-01')
DATA = ROOT / 'data' / 'sim' / 'segments'
OUT  = ROOT / 'out'
OUT.mkdir(exist_ok=True)

# parameters straight from PARAM_BY_PLATFORM (read via grep, not hand-written —
# we cannot import code/ as it isn't on sys.path canonically; values copied
# verbatim from code/parameters.py).
PARAMS = {
    'FORD_MUSTANG_MACH_E_MK1': dict(
        L=2.984, m=2336.0, I_z=4879.05,
        l_f=1.3130, l_r=1.671,
        C_af=286_551.0, C_ar=355_912.0, i_s=17.0,
    ),
    'FORD_F_150_LIGHTNING_MK1': dict(
        L=3.70, m=3084.0, I_z=9903.37,
        l_f=1.628, l_r=2.072,
        C_af=378_307.0, C_ar=469_878.0, i_s=16.9,
    ),
}

DT = 0.02  # 50 Hz

def kus(p):
    """Understeer gradient K_us [s^2/m]."""
    L = p['L']
    return (p['m'] * (p['l_r']*p['C_ar'] - p['l_f']*p['C_af'])
            / (L*L * p['C_af'] * p['C_ar']))

def regime_masks(yaw_meas, v):
    """Return dict regime -> bool mask."""
    dyaw = np.gradient(yaw_meas, DT)
    moving = v > 2.0
    cornering = np.abs(yaw_meas) >= 0.05
    transient = np.abs(dyaw) >= 0.2
    straight  = moving & ~cornering
    steady    = moving &  cornering & ~transient
    trans_msk = moving &  cornering &  transient
    return dict(straight=straight, steady=steady, transient=trans_msk,
                all=moving)

def estimate_lag(pred, meas, max_lag=10):
    """Integer-sample lag that maximises Pearson corr(pred shifted by k, meas).
    Positive k => prediction leads measurement; shift predictions forward by k.
    Restrict to cornering samples to get a meaningful lag.
    """
    pred = pred - np.nanmean(pred)
    meas = meas - np.nanmean(meas)
    n = len(pred)
    if n < 4*max_lag:
        return 0
    best_k, best_c = 0, -np.inf
    for k in range(-max_lag, max_lag+1):
        if k >= 0:
            a = pred[:n-k]; b = meas[k:]
        else:
            a = pred[-k:];  b = meas[:n+k]
        if len(a) < 50: continue
        sa, sb = a.std(), b.std()
        if sa < 1e-9 or sb < 1e-9: continue
        c = float(np.mean(a*b)/(sa*sb))
        if c > best_c:
            best_c, best_k = c, k
    return best_k

def shift_series(x, k):
    """Shift x by k samples (k>0 => move forward in time, pad NaN)."""
    y = np.full_like(x, np.nan, dtype=float)
    if k == 0:
        return x.copy()
    if k > 0:
        y[k:] = x[:-k]
    else:
        y[:k] = x[-k:]
    return y

def rmse(a, b):
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 5: return np.nan, int(m.sum())
    e = a[m] - b[m]
    return float(np.sqrt(np.mean(e*e))), int(m.sum())

def load_segments(platform, limit=None):
    pat = str(DATA / platform / '*' / '*' / '*' / 'sim.csv')
    files = sorted(glob.glob(pat))
    if limit: files = files[:limit]
    return files

def process_platform(platform, limit=None):
    p = PARAMS[platform]
    K = kus(p)
    L = p['L']
    files = load_segments(platform, limit=limit)
    rows = []
    for f in files:
        try:
            df = pd.read_csv(f)
        except Exception as e:
            continue
        if 'yaw_rate_meas_rads' not in df.columns:
            continue
        v       = df['v_mps'].to_numpy()
        delta   = df['delta_road_rad'].to_numpy()
        meas    = df['yaw_rate_meas_rads'].to_numpy()
        pred_v0 = df['yaw_rate_pred_rads'].to_numpy()
        # quick sanity: skip nearly-stationary segments
        if np.nanmedian(v) < 2.0:
            continue
        mks = regime_masks(meas, v)

        # V0: as-is residual
        res_v0 = pred_v0 - meas

        # V1: per-segment bias removal (mean of residual over moving samples)
        bias = np.nanmean(res_v0[mks['all']])
        pred_v1 = pred_v0 - bias

        # V2: latency alignment (estimate on cornering samples)
        corner_mask = mks['steady'] | mks['transient']
        if corner_mask.sum() > 100:
            lag = estimate_lag(pred_v1[corner_mask], meas[corner_mask], max_lag=8)
        else:
            lag = 0
        # apply same shift to whole segment
        pred_v2 = shift_series(pred_v1, lag)

        # V3: ST steady-state gain prediction instead of KS kinematic gain.
        # psi_dot_ss = v * delta / (L * (1 + K_us * v^2))
        pred_v3_raw = v * delta / (L * (1.0 + K * v*v))
        # Apply the V1 bias and V2 lag too (so V3 is "everything together")
        pred_v3 = pred_v3_raw - np.nanmean((pred_v3_raw - meas)[mks['all']])
        pred_v3 = shift_series(pred_v3, lag)

        # Score each variant per regime
        preds = dict(V0=pred_v0, V1=pred_v1, V2=pred_v2, V3=pred_v3)
        rec = dict(file=f, platform=platform, n=len(df), lag=lag, bias=bias, K_us=K)
        for vname, pr in preds.items():
            for rname, msk in mks.items():
                r, n = rmse(pr[msk], meas[msk])
                rec[f'{vname}_{rname}_rmse'] = r
                rec[f'{vname}_{rname}_n']    = n
        rows.append(rec)
    return pd.DataFrame(rows)

def aggregate(df):
    """Sample-weighted pooled RMSE: sqrt( sum(n_i * rmse_i^2) / sum(n_i) )."""
    regimes = ['straight','steady','transient','all']
    variants = ['V0','V1','V2','V3']
    out = {}
    for v in variants:
        out[v] = {}
        for r in regimes:
            n_col = f'{v}_{r}_n'
            r_col = f'{v}_{r}_rmse'
            ns = df[n_col].fillna(0).to_numpy()
            rs = df[r_col].fillna(0).to_numpy()
            num = float(np.sum(ns * rs*rs))
            den = float(np.sum(ns))
            out[v][r] = (np.sqrt(num/den) if den > 0 else np.nan, int(den))
    return out

def fmt_table(agg):
    regimes = ['straight','steady','transient','all']
    variants = ['V0','V1','V2','V3']
    # marginal: V0->V1, V1->V2, V2->V3 on 'all'
    lines = []
    lines.append("| Variant | straight RMSE | steady RMSE | transient RMSE | all RMSE | Δ vs prev (all) |")
    lines.append("|---|---|---|---|---|---|")
    prev_all = None
    for v in variants:
        cells = []
        for r in regimes:
            val, n = agg[v][r]
            cells.append(f"{val*1000:.2f} mrad/s (n={n})")
        cur = agg[v]['all'][0]
        if prev_all is None:
            delta = "—"
        else:
            d = (prev_all - cur)*1000
            pct = (prev_all - cur)/prev_all*100 if prev_all>0 else 0
            delta = f"{d:+.2f} mrad/s ({pct:+.1f}%)"
        lines.append(f"| {v} | " + " | ".join(cells) + f" | {delta} |")
        prev_all = cur
    return "\n".join(lines)

def main():
    summary = {}
    for plat in PARAMS:
        print(f"== {plat} ==", flush=True)
        df = process_platform(plat)
        df.to_csv(OUT / f'per_segment_{plat}.csv', index=False)
        agg = aggregate(df)
        summary[plat] = agg
        # Save aggregate
        with open(OUT / f'agg_{plat}.json', 'w') as f:
            json.dump({k: {r: list(v) for r,v in d.items()} for k,d in agg.items()}, f, indent=2)
        print(fmt_table(agg))
        print()
        # log K_us
        K = kus(PARAMS[plat])
        med_lag = df['lag'].median() if len(df) else np.nan
        med_bias = df['bias'].median() if len(df) else np.nan
        print(f"K_us = {K:.5f} s^2/m   median per-seg lag = {med_lag} samples ({med_lag*DT*1000:.0f} ms)   median bias = {med_bias*1000:.3f} mrad/s")
        print()
    with open(OUT / 'summary.json','w') as f:
        json.dump({plat:{v:{r:list(rr) for r,rr in d.items()} for v,d in agg.items()}
                   for plat, agg in summary.items()}, f, indent=2)

if __name__ == '__main__':
    main()
