"""Run the lateral-fidelity variant ladder on Mach-E segments.

Outputs CSVs to out/ and prints a markdown summary.
"""
from __future__ import annotations
import sys
import json
from pathlib import Path

MOD_DIR = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-3/agent-02")
sys.path.insert(0, str(MOD_DIR / "code"))
sys.path.insert(0, str(MOD_DIR / "skills" / "lateral-fidelity-triage"))

import numpy as np
import pandas as pd

import triage
from parameters import PARAM_BY_PLATFORM

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
DATA_ROOT = MOD_DIR / "data" / "sim" / "segments" / PLATFORM
OUT = MOD_DIR / "out"
OUT.mkdir(exist_ok=True)

params = PARAM_BY_PLATFORM[PLATFORM]
L = params.L
l_f = params.l_f
l_r = params.l_r
m = params.m
I_z = params.I_z
C_af_prior = params.C_alpha_f
C_ar_prior = params.C_alpha_r

# Collect segments
seg_paths = sorted(DATA_ROOT.rglob("sim.csv"))
print(f"Found {len(seg_paths)} {PLATFORM} segments")

df = triage.load_many(seg_paths)
print(f"Loaded {len(df):,} rows across {df['__source__'].nunique()} segments")

# Regime mask shared across all variants
reg = triage.regime_mask(df)
df["regime"] = reg

def per_regime(resid: np.ndarray) -> dict:
    out = {"overall": triage.rmse(resid)}
    for r in ("straight", "steady", "transient"):
        mask = (reg == r).to_numpy()
        out[r] = triage.rmse(resid[mask]) if mask.any() else float("nan")
    return out

results = {}

# V0 — baseline: as-is yaw_rate_resid_rads
resid_v0 = df["yaw_rate_resid_rads"].to_numpy()
results["V0"] = per_regime(resid_v0)
print("V0:", results["V0"])

# V1 — KS recalibrated with canonical L + per-segment yaw-gyro bias on straight samples
v = df["v_mps"].to_numpy()
delta = df["delta_road_rad"].to_numpy()
meas = df["yaw_rate_meas_rads"].to_numpy()

ks_pred = triage.ks_yaw_rate(v, delta, L)
resid_ks = ks_pred - meas

# per-segment straight-line bias
bias = np.zeros(len(df))
straight_mask = (reg == "straight").to_numpy()
seg_ids = df["__source__"].to_numpy()
biases_log = {}
for seg in df["__source__"].unique():
    seg_mask = (seg_ids == seg)
    s_mask = seg_mask & straight_mask
    if s_mask.sum() > 5:
        b = float(np.nanmean(resid_ks[s_mask]))
    else:
        b = 0.0
    bias[seg_mask] = b
    biases_log[seg] = b

resid_v1 = resid_ks - bias
results["V1"] = per_regime(resid_v1)
print("V1:", results["V1"])

# V2 — Linear ST with prior C_alpha
st_pred_prior = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, C_af_prior, C_ar_prior)
# correlation sign sanity check on cornering samples
corner = (reg != "straight").to_numpy()
corr_check = float(np.corrcoef(delta[corner], meas[corner])[0, 1])
print(f"corr(delta, meas) on corner samples = {corr_check:.3f}")

resid_st_prior_raw = st_pred_prior - meas
# apply same per-segment straight-line bias subtraction as V1 (so V1's gain isn't double-counted)
bias_st = np.zeros(len(df))
for seg in df["__source__"].unique():
    seg_mask = (seg_ids == seg)
    s_mask = seg_mask & straight_mask
    if s_mask.sum() > 5:
        b = float(np.nanmean(resid_st_prior_raw[s_mask]))
    else:
        b = 0.0
    bias_st[seg_mask] = b
resid_v2 = resid_st_prior_raw - bias_st
results["V2"] = per_regime(resid_v2)
print("V2:", results["V2"])

# V3 — Linear ST with fit C_alpha
cf_fit, cr_fit, pegged = triage.fit_c_alpha(df, L, l_f, l_r, m, I_z)
print(f"Fit C_alpha_f = {cf_fit:.0f}, C_alpha_r = {cr_fit:.0f} (pegged={pegged})")
st_pred_fit = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, cf_fit, cr_fit)
resid_st_fit_raw = st_pred_fit - meas
bias_st_fit = np.zeros(len(df))
for seg in df["__source__"].unique():
    seg_mask = (seg_ids == seg)
    s_mask = seg_mask & straight_mask
    if s_mask.sum() > 5:
        b = float(np.nanmean(resid_st_fit_raw[s_mask]))
    else:
        b = 0.0
    bias_st_fit[seg_mask] = b
resid_v3 = resid_st_fit_raw - bias_st_fit
results["V3"] = per_regime(resid_v3)
print("V3:", results["V3"])

# V4 — residual learner on V3 residuals, LOO segment CV
df_v3 = df.copy()
df_v3["v3_resid"] = resid_v3
try:
    oof_pred, info = triage.residual_learner_loo(df_v3, residual_col="v3_resid")
    resid_v4 = resid_v3 - oof_pred
    results["V4"] = per_regime(resid_v4)
    print("V4:", results["V4"], "info:", info)
except Exception as e:
    print(f"V4 failed: {e}")
    results["V4"] = None

# Save table
with open(OUT / "ladder_results.json", "w") as f:
    json.dump({k: v for k, v in results.items()}, f, indent=2)

# Print markdown table
def fmt(x):
    return f"{x:.4f}" if x is not None and np.isfinite(x) else "n/a"

vorder = ["V0", "V1", "V2", "V3", "V4"]
print()
print("| Variant | Overall | Straight | Steady corner | Transient corner | Marginal drop (overall) |")
print("|---|---|---|---|---|---|")
prev = results["V0"]["overall"]
for v in vorder:
    r = results[v]
    if r is None:
        print(f"| {v} | regression (skipped) | | | | |")
        continue
    md = prev - r["overall"]
    print(f"| {v} | {fmt(r['overall'])} | {fmt(r['straight'])} | {fmt(r['steady'])} | {fmt(r['transient'])} | {fmt(md)} |")
    prev = r["overall"]

# Save bias log
with open(OUT / "v1_bias_per_segment.json", "w") as f:
    json.dump(biases_log, f, indent=2)

print()
print(f"corr_check = {corr_check}")
print(f"C_alpha fit: cf={cf_fit:.0f}, cr={cr_fit:.0f}, pegged={pegged}")
print(f"prior:       cf={C_af_prior}, cr={C_ar_prior}")
