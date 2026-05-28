#!/usr/bin/env python3
"""Run the lateral-fidelity-triage variant ladder on Mach-E segments."""
from __future__ import annotations
import sys
from pathlib import Path
import glob
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-3/agent-01")
sys.path.insert(0, str(ROOT / "skills" / "lateral-fidelity-triage"))
sys.path.insert(0, str(ROOT / "code"))

import triage  # noqa: E402
from parameters import PARAM_BY_PLATFORM  # noqa: E402

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
p = PARAM_BY_PLATFORM[PLATFORM]
L = p.L
l_f = p.l_f
l_r = p.l_r
m = p.m
I_z = p.I_z
C_alpha_f0 = p.C_alpha_f
C_alpha_r0 = p.C_alpha_r

# Find Mach-E csvs, limit for runtime
pattern = str(ROOT / "data" / "sim" / "segments" / PLATFORM / "*" / "*" / "*" / "sim.csv")
all_csvs = sorted(glob.glob(pattern))
print(f"Found {len(all_csvs)} Mach-E csvs; using a sample.")
# Use first 30 for speed
csvs = all_csvs[:30]

df = triage.load_many(csvs)
print(f"Loaded {len(df)} rows across {df['__source__'].nunique()} segments")

reg = triage.regime_mask(df)
df["regime"] = reg.values

# ----- V0: baseline from existing yaw_rate_resid_rads as-is -----
v0_overall = triage.rmse(df["yaw_rate_resid_rads"])
v0_by_reg = {r: triage.rmse(df.loc[df.regime == r, "yaw_rate_resid_rads"]) for r in ("straight", "steady", "transient")}
print("V0 overall:", v0_overall, v0_by_reg)

# ----- V1: KS recalibrated + per-segment yaw-gyro bias -----
v = df["v_mps"].to_numpy()
delta = df["delta_road_rad"].to_numpy()
meas = df["yaw_rate_meas_rads"].to_numpy()

ks_pred = triage.ks_yaw_rate(v, delta, L)
# per-segment bias from straight-line samples
df["__ks_pred__"] = ks_pred
df["__ks_resid__"] = ks_pred - meas
bias = {}
for src, g in df.groupby("__source__"):
    straight = g[np.abs(g["delta_road_rad"]) < 0.01]
    if len(straight) > 0:
        bias[src] = straight["__ks_resid__"].mean()
    else:
        bias[src] = 0.0
biases_arr = df["__source__"].map(bias).to_numpy()
v1_pred = ks_pred - biases_arr
v1_resid = v1_pred - meas
df["v1_pred"] = v1_pred
df["v1_resid"] = v1_resid
v1_overall = triage.rmse(v1_resid)
v1_by_reg = {r: triage.rmse(df.loc[df.regime == r, "v1_resid"]) for r in ("straight", "steady", "transient")}
print("V1 overall:", v1_overall, v1_by_reg)

# ----- V2: Linear ST with prior Cα -----
v2_pred = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, C_alpha_f0, C_alpha_r0)
# also subtract per-segment bias estimated on straight-line of v2_pred-meas
df["__v2_pred_raw__"] = v2_pred
df["__v2_resid_raw__"] = v2_pred - meas
bias2 = {}
for src, g in df.groupby("__source__"):
    straight = g[np.abs(g["delta_road_rad"]) < 0.01]
    if len(straight) > 0:
        bias2[src] = straight["__v2_resid_raw__"].mean()
    else:
        bias2[src] = 0.0
biases2_arr = df["__source__"].map(bias2).to_numpy()
v2_pred = v2_pred - biases2_arr
v2_resid = v2_pred - meas
df["v2_pred"] = v2_pred
df["v2_resid"] = v2_resid
v2_overall = triage.rmse(v2_resid)
v2_by_reg = {r: triage.rmse(df.loc[df.regime == r, "v2_resid"]) for r in ("straight", "steady", "transient")}
print("V2 overall:", v2_overall, v2_by_reg)

# ----- V3: Linear ST with fit Cα -----
cf, cr, pegged = triage.fit_c_alpha(df, L, l_f, l_r, m, I_z)
print(f"V3 fit C_alpha_f={cf:.0f}, C_alpha_r={cr:.0f}, pegged={pegged}")
v3_pred_raw = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, cf, cr)
df["__v3_pred_raw__"] = v3_pred_raw
df["__v3_resid_raw__"] = v3_pred_raw - meas
bias3 = {}
for src, g in df.groupby("__source__"):
    straight = g[np.abs(g["delta_road_rad"]) < 0.01]
    if len(straight) > 0:
        bias3[src] = straight["__v3_resid_raw__"].mean()
    else:
        bias3[src] = 0.0
biases3_arr = df["__source__"].map(bias3).to_numpy()
v3_pred = v3_pred_raw - biases3_arr
v3_resid = v3_pred - meas
df["v3_pred"] = v3_pred
df["v3_resid"] = v3_resid
v3_overall = triage.rmse(v3_resid)
v3_by_reg = {r: triage.rmse(df.loc[df.regime == r, "v3_resid"]) for r in ("straight", "steady", "transient")}
print("V3 overall:", v3_overall, v3_by_reg)

# ----- V4: residual learner LOO on V3 residuals -----
# train on v3_resid
df_for_learner = df.copy()
df_for_learner["yaw_rate_resid_rads"] = df["v3_resid"]
oof, info = triage.residual_learner_loo(df_for_learner, residual_col="yaw_rate_resid_rads")
v4_pred = df["v3_pred"].to_numpy() + oof
v4_resid = v4_pred - meas
df["v4_pred"] = v4_pred
df["v4_resid"] = v4_resid
v4_overall = triage.rmse(v4_resid)
v4_by_reg = {r: triage.rmse(df.loc[df.regime == r, "v4_resid"]) for r in ("straight", "steady", "transient")}
print("V4 overall:", v4_overall, v4_by_reg, "oof_info:", info)

# Marginal accounting
marginals = {
    "V1": v0_overall - v1_overall,
    "V2": v1_overall - v2_overall,
    "V3": v2_overall - v3_overall,
    "V4": v3_overall - v4_overall,
}
total_drop = v0_overall - v4_overall
sum_marg = sum(marginals.values())
print("Marginals:", marginals)
print(f"Total V0->V4: {total_drop:.6f}; sum marginals: {sum_marg:.6f}")

# Save results table
results = {
    "V0": {"overall": v0_overall, **v0_by_reg},
    "V1": {"overall": v1_overall, **v1_by_reg},
    "V2": {"overall": v2_overall, **v2_by_reg},
    "V3": {"overall": v3_overall, **v3_by_reg},
    "V4": {"overall": v4_overall, **v4_by_reg},
}
pd.DataFrame(results).T.to_csv(ROOT / "out" / "ladder_results.csv")
print("\n=== TABLE ===")
print(pd.DataFrame(results).T)

# Determine best variant
candidates = {"V1": v1_overall, "V2": v2_overall, "V3": v3_overall, "V4": v4_overall}
best = min(candidates, key=candidates.get)
print(f"\nBest variant: {best} with RMSE={candidates[best]:.5f}")

# Save best variant as CSV for sensor
best_col = best.lower() + "_pred"
out_df = pd.DataFrame({
    "yaw_rate_pred_rads": df[best_col],
    "yaw_rate_meas_rads": meas,
    "delta_road_rad": delta,
    "yaw_rate_resid_rads": df["yaw_rate_resid_rads"].values,
})
out_path = ROOT / "out" / f"best_variant_{best}.csv"
out_df.to_csv(out_path, index=False)
print(f"Saved best variant CSV to {out_path}")
print(f"V0 baseline for sensor: {v0_overall:.6f}")
