"""Debug fit_c_alpha and explore ST variant performance."""
from __future__ import annotations
import sys, random
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOD = HERE.parent
sys.path.insert(0, str(MOD / "skills" / "lateral-fidelity-triage"))
sys.path.insert(0, str(MOD / "code"))

import numpy as np, pandas as pd
import triage as T
from parameters import PARAM_BY_PLATFORM
from scipy.optimize import minimize

P = PARAM_BY_PLATFORM["FORD_MUSTANG_MACH_E_MK1"]
SEG_ROOT = MOD / "data" / "sim" / "segments" / "FORD_MUSTANG_MACH_E_MK1"
csvs = sorted(SEG_ROOT.rglob("sim.csv"))
random.seed(0); sample = random.sample(csvs, k=25); sample.sort()
df = T.load_many(sample)

v = df["v_mps"].to_numpy(); d = df["delta_road_rad"].to_numpy(); meas = df["yaw_rate_meas_rads"].to_numpy()

# Sanity: how does pred (in csv) compare to KS recomputed?
pred_csv = df["yaw_rate_pred_rads"].to_numpy()
ks_re = T.ks_yaw_rate(v, d, P.L)
print("CSV pred vs recompute KS — corr:", np.corrcoef(pred_csv, ks_re)[0,1])
print("RMSE diff pred_csv vs ks_re:", T.rmse(pred_csv - ks_re))
print("RMSE pred_csv - meas:", T.rmse(pred_csv - meas))
print("RMSE ks_re - meas:   ", T.rmse(ks_re - meas))

# Now grid-search Cα to confirm optimum
def loss(cf, cr):
    pred = T.linear_st_yaw_rate(v, d, P.L, P.l_f, P.l_r, P.m, P.I_z, cf, cr)
    return T.rmse(pred - meas)

grid = np.geomspace(5e4, 5e5, 9)
best = (None, None, 1e9)
for cf in grid:
    for cr in grid:
        l = loss(cf, cr)
        if l < best[2]:
            best = (cf, cr, l)
print("grid best:", best)
print("loss at prior Cα:", loss(P.C_alpha_f, P.C_alpha_r))
print("loss at x0:", loss(1.5e5, 1.5e5))
print("loss KS:", T.rmse(ks_re - meas))

# Also try L-BFGS-B from prior
res = minimize(lambda x: loss(*x), x0=[P.C_alpha_f, P.C_alpha_r], method="L-BFGS-B",
               bounds=[(5e4,5e5),(5e4,5e5)])
print("L-BFGS-B from prior:", res.x, res.fun)
