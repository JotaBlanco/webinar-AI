"""Run V0→V4 lateral-fidelity ladder on Mach-E sim segments."""
from __future__ import annotations
import sys, os, json, random
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOD = HERE.parent
sys.path.insert(0, str(MOD / "skills" / "lateral-fidelity-triage"))
sys.path.insert(0, str(MOD / "code"))

import numpy as np
import pandas as pd

import triage as T
from parameters import PARAM_BY_PLATFORM

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
P = PARAM_BY_PLATFORM[PLATFORM]

SEG_ROOT = MOD / "data" / "sim" / "segments" / PLATFORM
csvs = sorted(SEG_ROOT.rglob("sim.csv"))
print(f"Found {len(csvs)} segments")

# Pick a manageable sample (deterministic) — ~25 segments
random.seed(0)
sample = random.sample(csvs, k=min(25, len(csvs)))
sample.sort()

df = T.load_many(sample)
print(f"Loaded rows: {len(df)} across {df['__source__'].nunique()} segments")
print("columns:", list(df.columns))

# Sanity / sign check on a corner sample
for s in df["__source__"].unique()[:3]:
    sub = df[df["__source__"] == s]
    c = sub["delta_road_rad"].corr(sub["yaw_rate_meas_rads"])
    print(f"  corr(delta,yaw_meas) {Path(s).parent.name}: {c:+.3f}")

reg = T.regime_mask(df)
df = df.assign(regime=reg.values)

def regime_rmse(resid):
    out = {"overall": T.rmse(resid)}
    for r in ("straight", "steady", "transient"):
        mask = (df["regime"] == r).to_numpy()
        out[r] = T.rmse(np.asarray(resid)[mask]) if mask.any() else float("nan")
    return out

results = {}

# ---- V0 baseline: precomputed residual
v0_resid = df["yaw_rate_resid_rads"].to_numpy()
results["V0_baseline"] = regime_rmse(v0_resid)

# ---- V1 KS recalibrated, with per-segment yaw-gyro bias subtraction on straights
v = df["v_mps"].to_numpy()
delta = df["delta_road_rad"].to_numpy()
meas = df["yaw_rate_meas_rads"].to_numpy()
ks_pred = T.ks_yaw_rate(v, delta, P.L)
v1_pred = ks_pred.copy()
# per-segment straight bias
bias_table = {}
for seg, idx in df.groupby("__source__").indices.items():
    idx = np.asarray(idx)
    straight = np.abs(delta[idx]) < 0.01
    sidx = idx[straight]
    if sidx.size > 50:
        bias = float(np.mean(ks_pred[sidx] - meas[sidx]))
    else:
        bias = 0.0
    bias_table[seg] = bias
    v1_pred[idx] = ks_pred[idx] - bias
v1_resid = v1_pred - meas
results["V1_ks_recal+bias"] = regime_rmse(v1_resid)

# ---- V2 Linear ST with prior C_alpha
v2_pred = T.linear_st_yaw_rate(v, delta, P.L, P.l_f, P.l_r, P.m, P.I_z, P.C_alpha_f, P.C_alpha_r)
# apply same straight-bias subtraction per segment
v2_pred_bc = v2_pred.copy()
for seg, idx in df.groupby("__source__").indices.items():
    idx = np.asarray(idx)
    straight = np.abs(delta[idx]) < 0.01
    sidx = idx[straight]
    if sidx.size > 50:
        b = float(np.mean(v2_pred[sidx] - meas[sidx]))
    else:
        b = 0.0
    v2_pred_bc[idx] = v2_pred[idx] - b
v2_resid = v2_pred_bc - meas
results["V2_linearST_prior"] = regime_rmse(v2_resid)

# ---- V3 Linear ST with fit C_alpha
cf, cr, pegged = T.fit_c_alpha(df, P.L, P.l_f, P.l_r, P.m, P.I_z)
print(f"Fit C_alpha_f={cf:.0f}, C_alpha_r={cr:.0f}, pegged={pegged}")
v3_pred = T.linear_st_yaw_rate(v, delta, P.L, P.l_f, P.l_r, P.m, P.I_z, cf, cr)
v3_pred_bc = v3_pred.copy()
for seg, idx in df.groupby("__source__").indices.items():
    idx = np.asarray(idx)
    straight = np.abs(delta[idx]) < 0.01
    sidx = idx[straight]
    if sidx.size > 50:
        b = float(np.mean(v3_pred[sidx] - meas[sidx]))
    else:
        b = 0.0
    v3_pred_bc[idx] = v3_pred[idx] - b
v3_resid = v3_pred_bc - meas
results["V3_linearST_fit"] = regime_rmse(v3_resid)

# ---- V4 Residual learner on V3 residuals (LOO)
df_v3 = df.copy()
df_v3["yaw_rate_resid_v3"] = v3_resid
oof, info = T.residual_learner_loo(df_v3, residual_col="yaw_rate_resid_v3")
v4_resid = v3_resid - oof
results["V4_residual_learner"] = regime_rmse(v4_resid)

print()
print(f"{'variant':28s} {'overall':>10s} {'straight':>10s} {'steady':>10s} {'transient':>10s}")
for k, v_ in results.items():
    print(f"{k:28s} {v_['overall']:10.5f} {v_['straight']:10.5f} {v_['steady']:10.5f} {v_['transient']:10.5f}")

# Attribution (overall RMSE delta vs previous rung)
order = ["V0_baseline", "V1_ks_recal+bias", "V2_linearST_prior", "V3_linearST_fit", "V4_residual_learner"]
print()
print("Attribution (overall RMSE drop vs previous rung):")
prev = None
attribution = {}
for k in order:
    o = results[k]["overall"]
    if prev is None:
        attribution[k] = 0.0
    else:
        attribution[k] = prev - o  # positive = improvement
    prev = o
    print(f"  {k}: overall={o:.5f}, delta={attribution[k]:+.5f}")

baseline = results["V0_baseline"]["overall"]
final = results["V4_residual_learner"]["overall"]
print(f"\nTotal reduction: {baseline:.5f} -> {final:.5f}  ({(baseline-final)/baseline*100:.1f}% drop)")

# write intermediates
OUT = MOD / "out"
OUT.mkdir(exist_ok=True)
with open(OUT / "ladder_results.json", "w") as f:
    json.dump({"results": results, "attribution": attribution,
               "fit_c_alpha_f": cf, "fit_c_alpha_r": cr, "pegged": pegged,
               "n_segments": int(df["__source__"].nunique()),
               "n_rows": int(len(df)),
               "platform": PLATFORM}, f, indent=2)
print("wrote", OUT / "ladder_results.json")
