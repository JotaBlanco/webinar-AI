"""Refine fit with finer grid + held-out validation (75/25)."""
import sys
sys.path.insert(0, 'skills/score-model')
import numpy as np
import pandas as pd
from pathlib import Path
from score import _default_segment_paths, _platform_from_path

L_BY_PLAT = {
    'FORD_F_150_LIGHTNING_MK1': 3.70,
    'FORD_MUSTANG_MACH_E_MK1': 2.984,
}

paths = _default_segment_paths()


def load_platform(plat):
    pp = [p for p in paths if _platform_from_path(p) == plat]
    pp = sorted(pp)
    segs = []
    for p in pp:
        df = pd.read_csv(p)
        if 'yaw_rate_meas_rads' not in df.columns:
            continue
        segs.append(df)
    return segs


def shift_delta(delta, lag_samples):
    if lag_samples == 0:
        return delta.copy()
    if lag_samples > 0:
        out = np.empty_like(delta)
        out[lag_samples:] = delta[:-lag_samples]
        out[:lag_samples] = delta[0]
        return out
    L = -lag_samples
    out = np.empty_like(delta)
    out[:-L] = delta[L:]
    out[-L:] = delta[-1]
    return out


def eval_params(segs, L, K, alpha, lag):
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
    return np.sqrt(sum_sq / n), n


def search(plat):
    segs = load_platform(plat)
    L = L_BY_PLAT[plat]
    n_train = int(len(segs) * 0.75)
    # Deterministic split by sorting (paths already sorted)
    rng = np.random.default_rng(42)
    idx = np.arange(len(segs))
    rng.shuffle(idx)
    train_idx = idx[:n_train]
    dev_idx = idx[n_train:]
    train_segs = [segs[i] for i in train_idx]
    dev_segs = [segs[i] for i in dev_idx]
    print(f'\n=== {plat}: {len(train_segs)} train / {len(dev_segs)} dev ===')

    best = None
    for lag in range(0, 11):
        for K in np.linspace(0.0, 0.005, 51):
            for alpha in np.linspace(0.80, 1.30, 51):
                rmse, _ = eval_params(train_segs, L, K, alpha, lag)
                if best is None or rmse < best[0]:
                    best = (rmse, lag, K, alpha)
    print(f'  Train best: rmse={best[0]:.5f}  lag={best[1]} K={best[2]:.5f} alpha={best[3]:.4f}')
    dev_rmse, _ = eval_params(dev_segs, L, best[2], best[3], best[1])
    print(f'  Dev rmse:   {dev_rmse:.5f}')
    # Baseline V0 on dev for comparison
    v0_sum = 0.0; v0_n = 0
    for df in dev_segs:
        v = df['v_mps'].values
        yr_m = df['yaw_rate_meas_rads'].values
        yr_p = df['yaw_rate_pred_rads'].values
        m = v > 2.0
        v0_sum += float(((yr_p[m]-yr_m[m])**2).sum())
        v0_n += int(m.sum())
    print(f'  V0 dev rmse: {np.sqrt(v0_sum/v0_n):.5f}')
    return best


results = {}
for plat in L_BY_PLAT:
    results[plat] = search(plat)
print('\nFinal coeffs:', results)
