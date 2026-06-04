"""Inspect Mustang residuals — biggest cte."""
import sys, json
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-09")
sys.path.insert(0, str(ROOT / "code"))

import numpy as np
import pandas as pd

P = json.loads((ROOT / "out" / "fitted_coeffs_full.json").read_text())


def predict_for_seg(sim, p, delta0):
    delta = (sim["delta_road_rad"].to_numpy() - delta0) * p["g"]
    v = sim["v_mps"].to_numpy()
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
    t = sim["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (p["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
    return yr


def _per_segment_delta0(sim_df):
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < 0.03) & (v > 5.0)
    return float(sim_df.loc[mask, "delta_road_rad"].median()) if mask.sum() >= 50 else 0.0


plat = "FORD_MUSTANG_MACH_E_MK1"
p = P[plat]
segs_paths = sorted((ROOT / "data" / "sim" / "segments" / plat).glob("**/sim.csv"))

# Compute residual vs |a_y| -> understeer nonlinearity?
all_a_y = []
all_resid = []
all_v = []
all_yr_t = []
for path in segs_paths[:60]:
    sim = pd.read_csv(path)
    d0 = _per_segment_delta0(sim) if p["use_per_segment_delta0"] else p["delta0"]
    yr = predict_for_seg(sim, p, d0)
    truth = sim["yaw_rate_meas_rads"].to_numpy()
    v = sim["v_mps"].to_numpy()
    a_y = v * truth  # lateral accel from truth
    mask = v > 5
    all_a_y.extend(a_y[mask])
    all_resid.extend((yr - truth)[mask])
    all_v.extend(v[mask])
    all_yr_t.extend(truth[mask])

all_a_y = np.array(all_a_y)
all_resid = np.array(all_resid)
all_v = np.array(all_v)
all_yr_t = np.array(all_yr_t)
print(f"n={len(all_resid)}")
print(f"corr(resid, a_y)         = {np.corrcoef(all_a_y, all_resid)[0,1]:+.4f}")
print(f"corr(resid, |a_y|)       = {np.corrcoef(np.abs(all_a_y), all_resid)[0,1]:+.4f}")
print(f"corr(resid, a_y^2*sign)  = {np.corrcoef(all_a_y * np.abs(all_a_y), all_resid)[0,1]:+.4f}")
print(f"corr(resid, sign(yr)*v)  = {np.corrcoef(np.sign(all_yr_t)*all_v, all_resid)[0,1]:+.4f}")
print(f"corr(resid, yr_t)        = {np.corrcoef(all_yr_t, all_resid)[0,1]:+.4f}")
print(f"corr(resid, v)           = {np.corrcoef(all_v, all_resid)[0,1]:+.4f}")
print(f"corr(resid, v^2)         = {np.corrcoef(all_v*all_v, all_resid)[0,1]:+.4f}")
