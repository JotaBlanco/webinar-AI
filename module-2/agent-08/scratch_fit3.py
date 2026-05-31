"""Vectorized fit: for each lag, solve analytically for alpha, K via grid+LS.

Model: yr_pred = alpha * x  where  x(K) = v*delta_lag / (L*(1+K*v^2))
For fixed K, optimal alpha = (sum xy)/(sum x^2). RMSE follows.
Iterate over K grid + lag grid.
"""
import sys
sys.path.insert(0, 'skills/score-model')
import numpy as np
import pandas as pd
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
        segs.append((df['v_mps'].to_numpy(dtype=float),
                     df['delta_road_rad'].to_numpy(dtype=float),
                     df['yaw_rate_meas_rads'].to_numpy(dtype=float),
                     df['yaw_rate_pred_rads'].to_numpy(dtype=float)))
    return segs


def shift(a, lag):
    if lag == 0:
        return a
    if lag > 0:
        out = np.empty_like(a)
        out[lag:] = a[:-lag]
        out[:lag] = a[0]
        return out
    L = -lag
    out = np.empty_like(a)
    out[:-L] = a[L:]
    out[-L:] = a[-1]
    return out


def stack(segs, lag):
    Vs, Ds, YMs, YKs = [], [], [], []
    for v, d, ym, yk in segs:
        mask = v > 2.0
        d_lag = shift(d, lag)
        Vs.append(v[mask])
        Ds.append(d_lag[mask])
        YMs.append(ym[mask])
        YKs.append(yk[mask])
    return (np.concatenate(Vs), np.concatenate(Ds), np.concatenate(YMs), np.concatenate(YKs))


def fit_plat(plat):
    segs = load_platform(plat)
    L = L_BY_PLAT[plat]
    # 75/25 split
    rng = np.random.default_rng(42)
    idx = np.arange(len(segs))
    rng.shuffle(idx)
    n_train = int(len(segs) * 0.75)
    train_segs = [segs[i] for i in idx[:n_train]]
    dev_segs = [segs[i] for i in idx[n_train:]]
    print(f'\n=== {plat}  segs={len(segs)} (train={len(train_segs)} dev={len(dev_segs)}) L={L} ===')

    best = None
    K_grid = np.linspace(0.0, 0.005, 101)
    for lag in range(0, 12):
        v, d, ym, yk = stack(train_segs, lag)
        # For each K, x = v*d / (L*(1+K v^2)); alpha = (sum xy)/(sum x^2)
        v2 = v*v
        for K in K_grid:
            x = v * d / (L * (1.0 + K * v2))
            sxx = float((x*x).sum())
            sxy = float((x*ym).sum())
            if sxx == 0:
                continue
            alpha = sxy / sxx
            # RMSE
            r = alpha * x - ym
            rmse = np.sqrt((r*r).mean())
            if best is None or rmse < best[0]:
                best = (rmse, lag, float(K), float(alpha))
    print(f'  Train: rmse={best[0]:.5f} lag={best[1]} K={best[2]:.5f} alpha={best[3]:.4f}')

    # Dev eval
    v, d, ym, yk = stack(dev_segs, best[1])
    x = v * d / (L * (1.0 + best[2] * v*v))
    r = best[3]*x - ym
    dev_rmse = np.sqrt((r*r).mean())
    # V0 dev
    v_ = np.concatenate([v[v>2.0] for v, d, ym, yk in dev_segs])  # placeholder
    yr_m_dev = np.concatenate([ym[v_seg>2.0] for v_seg, d, ym, yk in dev_segs])
    yr_p_dev = np.concatenate([yk[v_seg>2.0] for v_seg, d, ym, yk in dev_segs])
    v0_rmse = np.sqrt(((yr_p_dev - yr_m_dev)**2).mean())
    print(f'  Dev: rmse={dev_rmse:.5f}  V0 dev rmse={v0_rmse:.5f}')
    return best


results = {}
for plat in L_BY_PLAT:
    results[plat] = fit_plat(plat)
print('\nFINAL:', results)
