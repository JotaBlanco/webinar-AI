"""Side-by-side V0 vs V1 (no lag) vs V2 (with lag) on a single fixed dev split."""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'skills' / 'score-model'))
sys.path.insert(0, str(ROOT / 'skills' / 'make-train-dev-split'))

import numpy as np
import pandas as pd
from score import score
from split import split

train, dev = split(dev_fraction=0.25, seed=42)
print(f"train={len(train)}  dev={len(dev)}")

with open(ROOT / 'final-model' / 'coeffs.json') as fh:
    C = json.load(fh)

def v0(sim_df, platform):
    return pd.DataFrame({'yaw_rate_pred_rads': sim_df['yaw_rate_pred_rads'].values}, index=sim_df.index)

def make_v(use_lag):
    def fn(sim_df, platform):
        p = C.get(platform, {"L":2.9,"g":1.0,"K_us":0,"delta0":0,"tau":0})
        L, g, K, d0, tau = p["L"], p["g"], p["K_us"], p["delta0"], p.get("tau",0.0)
        v = sim_df["v_mps"].to_numpy(float)
        d = sim_df["delta_road_rad"].to_numpy(float)
        t = sim_df["t_s"].to_numpy(float)
        yr = g * v * (d - d0) / (L + K * v * v)
        if use_lag and tau > 0 and len(t) > 1:
            dt = np.diff(t)
            y = yr.copy()
            for k in range(1, len(yr)):
                a = dt[k-1] / (tau + dt[k-1])
                y[k] = a*yr[k] + (1-a)*y[k-1]
            yr = y
        return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
    return fn

for name, fn in [('V0_baseline', v0), ('V1_no_lag', make_v(False)), ('V2_with_lag', make_v(True))]:
    r_train = score(fn, segment_paths=train)
    r_dev = score(fn, segment_paths=dev)
    r_all = score(fn)
    print(f"\n{name}:")
    print(f"  TRAIN  yr={r_train['yaw_rate_rmse']:.5f}  cte={r_train['cte_rmse']:.4f}  n={r_train['n_segments']}")
    print(f"  DEV    yr={r_dev['yaw_rate_rmse']:.5f}  cte={r_dev['cte_rmse']:.4f}  n={r_dev['n_segments']}")
    print(f"  ALL    yr={r_all['yaw_rate_rmse']:.5f}  cte={r_all['cte_rmse']:.4f}  n={r_all['n_segments']}")
    print(f"  DEV per_platform:")
    for plat, v in r_dev['per_platform'].items():
        print(f"    {plat}: yr={v['yaw_rate_rmse']:.5f}  cte={v['cte_rmse']:.4f}")
    print(f"  DEV per_regime: " + ", ".join(f"{k}:{v['yaw_rate_rmse']:.5f}" for k,v in r_dev['per_regime'].items()))
