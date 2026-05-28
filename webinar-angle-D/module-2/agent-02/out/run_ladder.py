"""Run the lateral-fidelity-triage ladder V0..V4 on Mach-E segments."""
from __future__ import annotations
import sys, glob, json, os
from pathlib import Path
import numpy as np
import pandas as pd

MODULE = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-2/agent-02")
sys.path.insert(0, str(MODULE / "skills" / "lateral-fidelity-triage"))
sys.path.insert(0, str(MODULE / "code"))

import triage  # noqa
from parameters import MACH_E  # noqa

DATA_ROOT = MODULE / "data" / "sim" / "segments" / "FORD_MUSTANG_MACH_E_MK1"

# Sample N segments deterministically
all_csvs = sorted(glob.glob(str(DATA_ROOT / "**" / "sim.csv"), recursive=True))
N = 25
rng = np.random.default_rng(42)
idx = rng.choice(len(all_csvs), size=min(N, len(all_csvs)), replace=False)
csvs = [all_csvs[i] for i in sorted(idx)]
print(f"Using {len(csvs)} of {len(all_csvs)} Mach-E segments")

df = triage.load_many(csvs)
print(f"Total rows: {len(df)}")
print(f"Columns: {sorted(df.columns)}")

# Operating contract sanity
p = MACH_E
print(f"Vehicle params: L={p.L} l_f={p.l_f} l_r={p.l_r} m={p.m} I_z={p.I_z} "
      f"C_af={p.C_alpha_f} C_ar={p.C_alpha_r}")

meas = df["yaw_rate_meas_rads"].to_numpy()
v = df["v_mps"].to_numpy()
delta = df["delta_road_rad"].to_numpy()

# ----- V0: baseline using pre-computed yaw_rate_resid -----
v0 = triage.per_regime_rmse(df, "yaw_rate_resid_rads")

# ----- V1: KS recalibrated w/ canonical L + per-segment straight-line bias removal -----
ks_pred = triage.ks_yaw_rate(v, delta, p.L)
df["pred_v1"] = ks_pred
df["resid_v1"] = df["pred_v1"] - df["yaw_rate_meas_rads"]
# per-segment straight bias
for src, sub in df.groupby("__source__"):
    mask = np.abs(sub["delta_road_rad"]) < 0.01
    bias = sub.loc[mask, "resid_v1"].mean() if mask.sum() > 0 else 0.0
    df.loc[df["__source__"] == src, "resid_v1"] -= bias
v1 = triage.per_regime_rmse(df, "resid_v1")

# ----- V2: Linear ST w/ prior C_alpha -----
st_pred = triage.linear_st_yaw_rate(
    v, delta, p.L, p.l_f, p.l_r, p.m, p.I_z, p.C_alpha_f, p.C_alpha_r
)
df["pred_v2"] = st_pred
df["resid_v2"] = df["pred_v2"] - df["yaw_rate_meas_rads"]
# also bias-correct per segment for fairness
for src, sub in df.groupby("__source__"):
    mask = np.abs(sub["delta_road_rad"]) < 0.01
    bias = sub.loc[mask, "resid_v2"].mean() if mask.sum() > 0 else 0.0
    df.loc[df["__source__"] == src, "resid_v2"] -= bias
v2 = triage.per_regime_rmse(df, "resid_v2")

# ----- V3: Linear ST with fit C_alpha -----
cf_fit, cr_fit, pegged = triage.fit_c_alpha(
    df, p.L, p.l_f, p.l_r, p.m, p.I_z
)
print(f"Fit C_alpha: cf={cf_fit:.0f} cr={cr_fit:.0f} pegged={pegged}")
st_pred_fit = triage.linear_st_yaw_rate(
    v, delta, p.L, p.l_f, p.l_r, p.m, p.I_z, cf_fit, cr_fit
)
df["pred_v3"] = st_pred_fit
df["resid_v3"] = df["pred_v3"] - df["yaw_rate_meas_rads"]
for src, sub in df.groupby("__source__"):
    mask = np.abs(sub["delta_road_rad"]) < 0.01
    bias = sub.loc[mask, "resid_v3"].mean() if mask.sum() > 0 else 0.0
    df.loc[df["__source__"] == src, "resid_v3"] -= bias
v3 = triage.per_regime_rmse(df, "resid_v3")

# ----- V4: residual learner on V3 residuals -----
oof, info = triage.residual_learner_loo(df, residual_col="resid_v3")
df["resid_v4"] = df["resid_v3"] - oof
v4 = triage.per_regime_rmse(df, "resid_v4")
print(f"V4 residual learner oof_rmse on V3 resid: {info['oof_rmse']:.5f}")

# Build summary table
import collections
results = collections.OrderedDict([
    ("V0_baseline", v0),
    ("V1_KS_recalib_bias", v1),
    ("V2_linearST_prior_Ca", v2),
    ("V3_linearST_fit_Ca", v3),
    ("V4_residual_learner", v4),
])

rows = []
prev_overall = None
for name, m in results.items():
    delta_o = (prev_overall - m["overall"]) if prev_overall is not None else 0.0
    rows.append({
        "variant": name,
        "overall": m["overall"],
        "straight": m["straight"],
        "steady": m["steady"],
        "transient": m["transient"],
        "delta_overall_vs_prev": delta_o,
    })
    prev_overall = m["overall"]

out_df = pd.DataFrame(rows)
out_df.to_csv(MODULE / "out" / "ladder_results.csv", index=False)
print("\n=== ladder results (RMSE rad/s) ===")
print(out_df.to_string(index=False))

# Save residuals
df[["__source__","t_s","yaw_rate_meas_rads","yaw_rate_resid_rads",
    "resid_v1","resid_v2","resid_v3","resid_v4"]].to_csv(
    MODULE / "out" / "residuals.csv", index=False)

with open(MODULE / "out" / "fit_info.json", "w") as f:
    json.dump({"cf_fit": cf_fit, "cr_fit": cr_fit, "pegged": pegged,
               "v4_oof_rmse_on_v3": info["oof_rmse"],
               "n_segments": len(csvs), "n_rows": len(df)}, f, indent=2)
print("Wrote out/ladder_results.csv, out/residuals.csv, out/fit_info.json")
