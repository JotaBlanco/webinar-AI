"""Run V0..V4 variant ladder on Ford Mach-E segments and emit metrics + CSV."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-4/agent-01")
sys.path.insert(0, str(ROOT / "skills" / "lateral-fidelity-triage"))
sys.path.insert(0, str(ROOT / "code"))

import triage  # noqa: E402
from parameters import PARAM_BY_PLATFORM  # noqa: E402

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
N_SEGMENTS = 40  # cap for speed

p = PARAM_BY_PLATFORM[PLATFORM]
L, l_f, l_r, m, I_z = p.L, p.l_f, p.l_r, p.m, p.I_z
C_alpha_f_prior, C_alpha_r_prior = p.C_alpha_f, p.C_alpha_r

seg_dir = ROOT / "data" / "sim" / "segments" / PLATFORM
all_csvs = sorted(seg_dir.rglob("sim.csv"))
csvs = all_csvs[:N_SEGMENTS]
print(f"Using {len(csvs)} of {len(all_csvs)} Mach-E segments")

df = triage.load_many(csvs)
print(f"Total rows: {len(df)}")

# ---- regime mask (constant across variants) ----
df["regime"] = triage.regime_mask(df)

# Inputs
v = df["v_mps"].to_numpy()
delta = df["delta_road_rad"].to_numpy()
meas = df["yaw_rate_meas_rads"].to_numpy()

def per_regime(resid):
    out = {"overall": triage.rmse(resid)}
    for r in ("straight", "steady", "transient"):
        mask = (df["regime"] == r).to_numpy()
        out[r] = triage.rmse(resid[mask]) if mask.any() else float("nan")
    return out

results = {}

# ---- V0: baseline, residual as stored ----
resid_v0 = df["yaw_rate_resid_rads"].to_numpy()
results["V0"] = per_regime(resid_v0)

# ---- V1: KS recalibrated. Use canonical L; subtract per-segment yaw-gyro bias on straight samples ----
pred_v1 = triage.ks_yaw_rate(v, delta, L)
# Bias subtraction per segment
biases = {}
for src, sub in df.groupby("__source__"):
    idx = sub.index.to_numpy()
    straight_mask = (sub["regime"] == "straight").to_numpy()
    if straight_mask.any():
        b = float(np.mean(pred_v1[idx][straight_mask] - meas[idx][straight_mask]))
    else:
        b = 0.0
    biases[src] = b
bias_arr = df["__source__"].map(biases).to_numpy()
pred_v1_corr = pred_v1 - bias_arr
resid_v1 = pred_v1_corr - meas
results["V1"] = per_regime(resid_v1)

# ---- V2: Linear ST with prior C_alpha ----
pred_v2 = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z,
                                    C_alpha_f_prior, C_alpha_r_prior)
# Apply same per-segment bias subtraction approach so V1 bias-correction carries forward.
biases_v2 = {}
for src, sub in df.groupby("__source__"):
    idx = sub.index.to_numpy()
    straight_mask = (sub["regime"] == "straight").to_numpy()
    if straight_mask.any():
        b = float(np.mean(pred_v2[idx][straight_mask] - meas[idx][straight_mask]))
    else:
        b = 0.0
    biases_v2[src] = b
bias_v2_arr = df["__source__"].map(biases_v2).to_numpy()
pred_v2_corr = pred_v2 - bias_v2_arr
resid_v2 = pred_v2_corr - meas
results["V2"] = per_regime(resid_v2)

# ---- V3: Linear ST with fit C_alpha ----
# The provided L-BFGS-B fit gets stuck due to a non-smooth loss surface near
# K_us·v² ≈ -1 (singular). Use a coarse grid as a robust fallback.
cf, cr, pegged = triage.fit_c_alpha(df, L, l_f, l_r, m, I_z)
print(f"L-BFGS-B fit: cf={cf:.0f} cr={cr:.0f} pegged={pegged} (likely stuck at x0)")

def _loss(cf_, cr_):
    pred = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, cf_, cr_)
    e = pred - meas
    e = e[np.isfinite(e)]
    return float(np.sqrt(np.mean(e**2)))

grid = np.linspace(5e4, 5e5, 19)
best = (cf, cr, _loss(cf, cr))
for gf in grid:
    for gr in grid:
        L_ = _loss(gf, gr)
        if L_ < best[2]:
            best = (gf, gr, L_)
cf, cr = best[0], best[1]
pegged = (abs(cf - 5e5) < 1.0) or (abs(cr - 5e5) < 1.0)
print(f"Grid-search fit: cf={cf:.0f} cr={cr:.0f} loss={best[2]:.5f} pegged={pegged}")
pred_v3 = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, cf, cr)
biases_v3 = {}
for src, sub in df.groupby("__source__"):
    idx = sub.index.to_numpy()
    straight_mask = (sub["regime"] == "straight").to_numpy()
    if straight_mask.any():
        b = float(np.mean(pred_v3[idx][straight_mask] - meas[idx][straight_mask]))
    else:
        b = 0.0
    biases_v3[src] = b
bias_v3_arr = df["__source__"].map(biases_v3).to_numpy()
pred_v3_corr = pred_v3 - bias_v3_arr
resid_v3 = pred_v3_corr - meas
results["V3"] = per_regime(resid_v3)

# ---- V4: residual learner on V3 residuals via LOO ----
# Use a separate dataframe view so we feed V3-residuals
df_v4 = df.copy()
df_v4["yaw_rate_resid_v3"] = resid_v3
oof, info = triage.residual_learner_loo(df_v4, residual_col="yaw_rate_resid_v3")
print(f"V4 residual learner OOF RMSE on residual itself: {info['oof_rmse']:.5f}")
# Apply correction: pred_v4 = pred_v3_corr - oof  → new resid = resid_v3 - oof
resid_v4 = resid_v3 - oof
# If oof has nan rows guard:
resid_v4 = np.where(np.isfinite(oof), resid_v4, resid_v3)
results["V4"] = per_regime(resid_v4)

# Save
out_path = ROOT / "out" / "ladder.json"
extra = {
    "platform": PLATFORM,
    "n_segments": len(csvs),
    "total_rows": int(len(df)),
    "L": L, "l_f": l_f, "l_r": l_r, "m": m, "I_z": I_z,
    "C_alpha_f_prior": C_alpha_f_prior, "C_alpha_r_prior": C_alpha_r_prior,
    "C_alpha_f_fit": cf, "C_alpha_r_fit": cr, "pegged": bool(pegged),
    "results": results,
    "regime_counts": {r: int((df["regime"] == r).sum()) for r in ("straight", "steady", "transient")},
}
out_path.write_text(json.dumps(extra, indent=2))
print(json.dumps(extra, indent=2))
