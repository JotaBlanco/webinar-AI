"""Sanity-check the C_alpha fit by grid-scanning."""
import sys, os, glob
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "skills", "lateral-fidelity-triage"))
sys.path.insert(0, os.path.join(ROOT, "code"))
import triage
from parameters import MACH_E as P
import pandas as pd

csvs = sorted(glob.glob(os.path.join(ROOT, "data", "sim", "segments", "FORD_MUSTANG_MACH_E_MK1", "**", "sim.csv"), recursive=True))[:12]
dfs = [triage.load_ford_sim(p).assign(__source__=p) for p in csvs]
df = pd.concat(dfs, ignore_index=True)

meas = df["yaw_rate_meas_rads"].to_numpy()
v = df["v_mps"].to_numpy()
delta = df["delta_road_rad"].to_numpy()

def loss(cf, cr):
    pred = triage.linear_st_yaw_rate(v, delta, P.L, P.l_f, P.l_r, P.m, P.I_z, cf, cr)
    e = pred - meas
    return float(np.sqrt(np.mean(e ** 2)))

grid = [5e4, 1e5, 1.5e5, 2e5, 2.86e5, 3.56e5, 4e5, 5e5]
print("loss table (rows=Cf, cols=Cr)")
print(" ", "  ".join(f"{c:.1e}" for c in grid))
best = (1e9, None)
for cf in grid:
    row = []
    for cr in grid:
        l = loss(cf, cr)
        row.append(f"{l:.5f}")
        if l < best[0]:
            best = (l, (cf, cr))
    print(f"{cf:.1e}", "  ".join(row))
print("best:", best)

# also: loss at openpilot prior
print("prior loss:", loss(P.C_alpha_f, P.C_alpha_r))
print("at x0 (1.5e5,1.5e5):", loss(1.5e5, 1.5e5))
