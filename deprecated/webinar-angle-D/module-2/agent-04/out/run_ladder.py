"""Run V0..V4 ladder on a Mach-E segment set."""
from __future__ import annotations
import sys, os, glob, json
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "skills", "lateral-fidelity-triage"))
sys.path.insert(0, os.path.join(ROOT, "code"))

import triage  # noqa: E402
from parameters import MACH_E  # noqa: E402

# pick first N Mach-E segments
PATTERN = os.path.join(ROOT, "data", "sim", "segments", "FORD_MUSTANG_MACH_E_MK1",
                       "**", "sim.csv")
csvs = sorted(glob.glob(PATTERN, recursive=True))
# trim to a manageable set with diversity (different devices/routes)
N = 12
csvs = csvs[:N]
print(f"Loading {len(csvs)} segments")

dfs = []
for p in csvs:
    df = triage.load_ford_sim(p)
    df["__source__"] = p
    dfs.append(df)
df = pd.concat(dfs, ignore_index=True)
print(f"Total rows: {len(df)}")

P = MACH_E
print(f"Mach-E params: L={P.L} l_f={P.l_f} l_r={P.l_r} m={P.m} I_z={P.I_z} Cf={P.C_alpha_f} Cr={P.C_alpha_r}")

# Diagnostic: correlation of delta vs yaw on cornering rows
reg = triage.regime_mask(df)
corn = df[reg != "straight"]
if len(corn):
    c = np.corrcoef(corn["delta_road_rad"], corn["yaw_rate_meas_rads"])[0, 1]
    print(f"corr(delta_road, yaw_meas) on cornering: {c:.3f}")

# ---------- V0 baseline (the residual already in the CSV) ----------
v0_resid = df["yaw_rate_resid_rads"].to_numpy()
v0_overall = triage.rmse(v0_resid)
v0_per = triage.per_regime_rmse(df, "yaw_rate_resid_rads")

# ---------- V1 KS recalibrated + per-segment straight-line yaw-bias ----------
ks_pred = triage.ks_yaw_rate(df["v_mps"], df["delta_road_rad"], P.L)
df["__v1_pred__"] = ks_pred
# per-segment yaw-gyro bias on straight rows
df["__v1_resid__"] = df["__v1_pred__"] - df["yaw_rate_meas_rads"]
straight = np.abs(df["delta_road_rad"]) < 0.01
biases = {}
for src, sub in df.groupby("__source__"):
    s = sub[straight.loc[sub.index]]
    b = float(s["__v1_resid__"].mean()) if len(s) else 0.0
    biases[src] = b
df["__v1_bias__"] = df["__source__"].map(biases)
df["__v1_resid__"] = df["__v1_pred__"] - df["__v1_bias__"] - df["yaw_rate_meas_rads"]
v1_overall = triage.rmse(df["__v1_resid__"])
v1_per = triage.per_regime_rmse(df, "__v1_resid__")

# ---------- V2 Linear ST with prior C_alpha ----------
st_pred = triage.linear_st_yaw_rate(
    df["v_mps"], df["delta_road_rad"],
    P.L, P.l_f, P.l_r, P.m, P.I_z,
    P.C_alpha_f, P.C_alpha_r,
)
df["__v2_pred__"] = st_pred
# apply same per-segment yaw bias correction (re-derive on straight rows)
df["__v2_resid_raw__"] = df["__v2_pred__"] - df["yaw_rate_meas_rads"]
biases2 = {}
for src, sub in df.groupby("__source__"):
    s = sub[straight.loc[sub.index]]
    b = float(s["__v2_resid_raw__"].mean()) if len(s) else 0.0
    biases2[src] = b
df["__v2_bias__"] = df["__source__"].map(biases2)
df["__v2_resid__"] = df["__v2_pred__"] - df["__v2_bias__"] - df["yaw_rate_meas_rads"]
v2_overall = triage.rmse(df["__v2_resid__"])
v2_per = triage.per_regime_rmse(df, "__v2_resid__")

# ---------- V3 Linear ST with fit C_alpha ----------
cf_fit, cr_fit, pegged = triage.fit_c_alpha(
    df, P.L, P.l_f, P.l_r, P.m, P.I_z,
)
print(f"V3 fit: C_alpha_f={cf_fit:.0f}  C_alpha_r={cr_fit:.0f}  pegged={pegged}")
st_pred_fit = triage.linear_st_yaw_rate(
    df["v_mps"], df["delta_road_rad"],
    P.L, P.l_f, P.l_r, P.m, P.I_z, cf_fit, cr_fit,
)
df["__v3_pred__"] = st_pred_fit
df["__v3_resid_raw__"] = df["__v3_pred__"] - df["yaw_rate_meas_rads"]
biases3 = {}
for src, sub in df.groupby("__source__"):
    s = sub[straight.loc[sub.index]]
    b = float(s["__v3_resid_raw__"].mean()) if len(s) else 0.0
    biases3[src] = b
df["__v3_bias__"] = df["__source__"].map(biases3)
df["__v3_resid__"] = df["__v3_pred__"] - df["__v3_bias__"] - df["yaw_rate_meas_rads"]
v3_overall = triage.rmse(df["__v3_resid__"])
v3_per = triage.per_regime_rmse(df, "__v3_resid__")

# ---------- V4 residual learner on V3 residuals ----------
df["__v3_resid_for_learner__"] = df["__v3_resid__"]
oof, info = triage.residual_learner_loo(df, residual_col="__v3_resid_for_learner__")
df["__v4_resid__"] = df["__v3_resid__"] - oof
v4_overall = triage.rmse(df["__v4_resid__"])
v4_per = triage.per_regime_rmse(df, "__v4_resid__")
print(f"V4 oof_rmse_of_learner_target={info['oof_rmse']:.6f}")

results = [
    ("V0_baseline_in_csv", v0_per),
    ("V1_KS_recalib+yawbias", v1_per),
    ("V2_LinearST_priorCa", v2_per),
    ("V3_LinearST_fitCa", v3_per),
    ("V4_residual_learner", v4_per),
]

print("\nVariant ladder (RMSE in rad/s)")
print(f"{'variant':30s} {'overall':>10s} {'straight':>10s} {'steady':>10s} {'transient':>10s}")
for name, per in results:
    print(f"{name:30s} {per['overall']:>10.5f} {per['straight']:>10.5f} {per['steady']:>10.5f} {per['transient']:>10.5f}")

# attribution = absolute reduction in overall RMSE attributable to that step
overalls = [per["overall"] for _, per in results]
attr = [overalls[0] - overalls[0]]  # V0 vs itself = 0
for i in range(1, len(overalls)):
    attr.append(overalls[i - 1] - overalls[i])
print("\nAttribution (Δ overall RMSE vs previous step, rad/s)")
for (name, _), a in zip(results, attr):
    print(f"  {name:30s} Δ = {a:+.5f}")

# dump intermediate
out_csv = os.path.join(HERE, "ladder_results.csv")
rows = []
for name, per in results:
    rows.append({"variant": name, **per})
pd.DataFrame(rows).to_csv(out_csv, index=False)
print(f"\nWrote {out_csv}")

# also save fit params
with open(os.path.join(HERE, "fit_params.json"), "w") as f:
    json.dump({
        "n_segments": len(csvs),
        "n_rows": int(len(df)),
        "C_alpha_f_fit": cf_fit,
        "C_alpha_r_fit": cr_fit,
        "pegged": pegged,
        "v0_overall_rmse": v0_overall,
        "v1_overall_rmse": v1_overall,
        "v2_overall_rmse": v2_overall,
        "v3_overall_rmse": v3_overall,
        "v4_overall_rmse": v4_overall,
        "attribution": dict(zip([r[0] for r in results], attr)),
    }, f, indent=2)
print("Wrote fit_params.json")
