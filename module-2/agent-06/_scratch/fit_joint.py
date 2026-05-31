"""Joint fit with lag: for each tau, refit (K, d0, scale) per platform."""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/make-train-dev-split"))
from split import split as make_split

L_BY = {'FORD_F_150_LIGHTNING_MK1': 3.70, 'FORD_MUSTANG_MACH_E_MK1': 2.984}

def lowpass(x, dt, tau):
    if tau <= 0:
        return x.copy()
    y = np.empty_like(x)
    y[0] = x[0]
    for i in range(1, len(x)):
        a = dt[i-1] / (tau + dt[i-1])
        y[i] = y[i-1] + a * (x[i] - y[i-1])
    return y

def load_filtered(paths, plat, tau):
    arrs = []
    for p in paths:
        if plat not in str(p): continue
        df = pd.read_csv(p)
        v = df['v_mps'].to_numpy(float)
        t = df['t_s'].to_numpy(float)
        delta = df['delta_road_rad'].to_numpy(float)
        yrm = df['yaw_rate_meas_rads'].to_numpy(float)
        if len(t) < 2: continue
        dt = np.diff(t)
        dt = np.append(dt, dt[-1])
        if tau > 0:
            delta_f = lowpass(delta, dt, tau)
        else:
            delta_f = delta
        m = v > 2.0
        arrs.append(np.column_stack([delta_f[m], v[m], yrm[m]]))
    return np.vstack(arrs)

train_paths, dev_paths = make_split(dev_fraction=0.25, seed=42)

results = {}
for plat, L in L_BY.items():
    print(f"\n=== {plat} ===")
    plat_best = (None, 0,0,1,1e9)
    for tau in [0.0, 0.03, 0.05, 0.06, 0.08, 0.10, 0.15]:
        arr = load_filtered(train_paths, plat, tau)
        delta = arr[:,0]; v = arr[:,1]; yrm = arr[:,2]
        # grid
        best=(0,0,1,1e9)
        for K in np.linspace(0, 0.004, 41):
            for d0 in np.linspace(-0.01, 0.01, 21):
                term = (v/L)*np.tan(delta - d0)/(1+K*v**2)
                sc = np.dot(term, yrm)/np.dot(term, term)
                mse = np.mean((sc*term - yrm)**2)
                if mse < best[3]:
                    best = (K, d0, sc, mse)
        # refine
        K,d0,sc,_ = best
        for Kx in np.linspace(max(0,K-0.0002), K+0.0002, 21):
            for d0x in np.linspace(d0-0.002, d0+0.002, 21):
                term = (v/L)*np.tan(delta - d0x)/(1+Kx*v**2)
                scx = np.dot(term, yrm)/np.dot(term, term)
                mse = np.mean((scx*term - yrm)**2)
                if mse < best[3]:
                    best = (Kx, d0x, scx, mse)
        K,d0,sc,mse = best
        rmse = np.sqrt(mse)
        print(f'  tau={tau:.3f}: K={K:.5e} d0={d0:.5f} scale={sc:.4f} TRAIN RMSE={rmse:.5f}')
        if rmse < plat_best[4]:
            plat_best = (tau, K, d0, sc, rmse)
    tau, K, d0, sc, _ = plat_best
    results[plat] = {"tau": float(tau), "K": float(K), "delta0": float(d0), "scale": float(sc), "L": L}
    print(f'  BEST tau={tau} K={K:.5e} d0={d0:.5f} scale={sc:.4f}')

with open(ROOT / "_scratch/coefs_joint.json", "w") as f:
    json.dump(results, f, indent=2)
print(json.dumps(results, indent=2))
