"""Fit per-platform linear bicycle (with understeer + bias) on a train split.

Model: yaw_rate = v * (delta - delta0) / (L + K_us * v^2)

Equivalently linearised about small angles via:  y * (L + K_us v^2) = v * (delta - delta0)
=> y*L + y*K_us*v^2 = v*delta - v*delta0
=> (v*delta) - (y*L) = K_us * (y*v^2) + delta0 * v
This is linear in (K_us, delta0). Solve by OLS.
"""
import os, glob, sys, json
import numpy as np, pandas as pd

ROOT = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-01'
os.chdir(ROOT)

L_BY_PLAT = {
    'FORD_F_150_LIGHTNING_MK1': 3.70,
    'FORD_MUSTANG_MACH_E_MK1': 2.984,
    'TESLA_MODEL_3': 2.875,
}

# Deterministic train/dev split: take half by sorted path index.
def split_paths(paths):
    paths = sorted(paths)
    # train = even-index, dev = odd-index
    train = [p for i,p in enumerate(paths) if i % 2 == 0]
    dev   = [p for i,p in enumerate(paths) if i % 2 == 1]
    return train, dev

results = {}
for plat, L in L_BY_PLAT.items():
    paths = sorted(glob.glob(f'data/sim/segments/{plat}/**/sim.csv', recursive=True))
    if not paths:
        continue
    # Tesla has no truth; skip fitting but record L.
    train, dev = split_paths(paths)
    # Accumulate samples
    V = []
    D = []
    Y = []
    for p in train:
        df = pd.read_csv(p)
        if 'yaw_rate_meas_rads' not in df.columns:
            continue
        v = df['v_mps'].to_numpy()
        d = df['delta_road_rad'].to_numpy()
        y = df['yaw_rate_meas_rads'].to_numpy()
        # quality filter: ignore very low speed (noise)
        m = (v > 3.0) & np.isfinite(v) & np.isfinite(d) & np.isfinite(y)
        V.append(v[m]); D.append(d[m]); Y.append(y[m])
    if not V:
        continue
    v = np.concatenate(V); d = np.concatenate(D); y = np.concatenate(Y)
    # OLS: y*L = v*delta - v*delta0 - y*K_us*v^2
    # Move unknowns to RHS:  v*delta - y*L = K_us*(y*v^2) + delta0*(v)
    rhs = v * d - y * L
    A = np.column_stack([y * v * v, v])
    # Least squares
    coef, *_ = np.linalg.lstsq(A, rhs, rcond=None)
    K_us, delta0 = coef
    print(f'{plat}: K_us={K_us:.5f}, delta0={delta0:.5f} rad ({np.degrees(delta0):.3f} deg)')
    # Evaluate model on train
    y_pred_train = v * (d - delta0) / (L + K_us * v * v)
    rmse_train = np.sqrt(np.mean((y_pred_train - y)**2))
    y_v0_train = (v / L) * np.tan(d)
    rmse_v0_train = np.sqrt(np.mean((y_v0_train - y)**2))
    print(f'   train RMSE V0={rmse_v0_train:.5f}, V1={rmse_train:.5f}')
    results[plat] = {'L': L, 'K_us': float(K_us), 'delta0': float(delta0)}

print(json.dumps(results, indent=2))
# Also include Tesla with neutral defaults
if 'TESLA_MODEL_3' not in results:
    results['TESLA_MODEL_3'] = {'L': 2.875, 'K_us': 0.0, 'delta0': 0.0}
with open(os.path.join(ROOT, 'work/coeffs_v1.json'), 'w') as f:
    json.dump(results, f, indent=2)
