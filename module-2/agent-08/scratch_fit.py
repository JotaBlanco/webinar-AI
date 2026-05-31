"""Per-platform fit of understeer coefficient K and lag.

Model: yr_pred(t) = (v(t) * delta_road(t - tau)) / (L * (1 + K * v^2))
Optionally a scale alpha: yr_pred = alpha * (v*delta_lag) / (L*(1+K*v^2))
"""
import sys
sys.path.insert(0, 'skills/score-model')
import numpy as np
import pandas as pd
from pathlib import Path
from score import _default_segment_paths, _platform_from_path, score

L_BY_PLAT = {
    'FORD_F_150_LIGHTNING_MK1': 3.70,
    'FORD_MUSTANG_MACH_E_MK1': 2.984,
}

paths = _default_segment_paths()


def load_platform(plat, limit=None):
    plat_paths = [p for p in paths if _platform_from_path(p) == plat]
    if limit:
        plat_paths = plat_paths[:limit]
    segs = []
    for p in plat_paths:
        df = pd.read_csv(p)
        if 'yaw_rate_meas_rads' not in df.columns:
            continue
        segs.append(df)
    return segs


def shift_delta(delta, lag_samples):
    """Positive lag: delta is shifted forward in time, so we use delta[t-lag] for current step."""
    if lag_samples == 0:
        return delta.copy()
    elif lag_samples > 0:
        # We assume sample i corresponds to delta value seen lag_samples earlier
        out = np.empty_like(delta)
        out[lag_samples:] = delta[:-lag_samples]
        out[:lag_samples] = delta[0]
        return out
    else:
        L = -lag_samples
        out = np.empty_like(delta)
        out[:-L] = delta[L:]
        out[-L:] = delta[-1]
        return out


def search_params(plat):
    segs = load_platform(plat)
    L = L_BY_PLAT[plat]
    # Stack samples for understeer fit
    print(f'\n=== {plat} ({len(segs)} segs, L={L}) ===')
    # Try grid: K in [0, 0.0003, ..., 0.005], lag in [0..8]
    best = None
    for lag in range(0, 9):
        for K in np.linspace(0.0, 0.004, 21):
            for alpha in [0.85, 0.9, 0.95, 1.0, 1.02, 1.05]:
                sum_sq = 0.0
                n = 0
                for df in segs:
                    v = df['v_mps'].values
                    delta = df['delta_road_rad'].values
                    yr_m = df['yaw_rate_meas_rads'].values
                    d_lag = shift_delta(delta, lag)
                    yr_pred = alpha * (v * d_lag) / (L * (1.0 + K * v * v))
                    mask = v > 2.0
                    r = yr_pred[mask] - yr_m[mask]
                    sum_sq += float((r*r).sum())
                    n += int(mask.sum())
                rmse = np.sqrt(sum_sq / n)
                if best is None or rmse < best[0]:
                    best = (rmse, lag, K, alpha)
    print(f'  best: rmse={best[0]:.5f}  lag={best[1]} samples  K={best[2]:.5f}  alpha={best[3]}')
    return best


for plat in L_BY_PLAT:
    search_params(plat)
