"""Sanity-check the C_alpha fit landscape."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
AGENT_ROOT = HERE.parent
sys.path.insert(0, str(AGENT_ROOT / "code"))
sys.path.insert(0, str(AGENT_ROOT / "skills" / "lateral-fidelity-triage"))
import triage  # noqa: E402
from parameters import PARAM_BY_PLATFORM  # noqa: E402

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
DATA_DIR = AGENT_ROOT / "data"

seg_csvs = sorted((DATA_DIR / "sim" / "segments" / PLATFORM).rglob("sim.csv"))[:80]
df = triage.load_many(seg_csvs).dropna(subset=["yaw_rate_meas_rads", "v_mps", "delta_road_rad"]).reset_index(drop=True)
p = PARAM_BY_PLATFORM[PLATFORM]

meas = df["yaw_rate_meas_rads"].to_numpy()
v = df["v_mps"].to_numpy()
delta = df["delta_road_rad"].to_numpy()

def loss(cf, cr):
    pred = triage.linear_st_yaw_rate(v, delta, p.L, p.l_f, p.l_r, p.m, p.I_z, cf, cr)
    e = pred - meas
    e = e[np.isfinite(e)]
    return float(np.sqrt(np.mean(e ** 2)))

# Grid sweep
print(f"{'Cf':>10} {'Cr':>10} {'rmse':>10}")
for cf in [5e4, 1e5, 1.5e5, 2e5, 286_551, 3.5e5, 5e5]:
    for cr in [5e4, 1e5, 1.5e5, 2e5, 355_912, 4e5, 5e5]:
        print(f"{cf:10.0f} {cr:10.0f} {loss(cf, cr):10.5f}")

# Also: pure KS
pred_ks = triage.ks_yaw_rate(v, delta, p.L)
err = pred_ks - meas
err = err[np.isfinite(err)]
print(f"\npure KS RMSE = {np.sqrt(np.mean(err**2)):.5f}")
