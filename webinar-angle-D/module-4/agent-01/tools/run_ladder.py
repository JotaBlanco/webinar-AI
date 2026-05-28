"""Driver: composes regime-segmentation + lateral-fidelity-triage skills."""
from __future__ import annotations
import sys, os
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "skills" / "lateral-fidelity-triage"))
sys.path.insert(0, str(ROOT / "skills" / "regime-segmentation"))
sys.path.insert(0, str(ROOT / "code"))

import segment   # regime-segmentation skill
import triage    # lateral-fidelity-triage skill
from parameters import PARAM_BY_PLATFORM

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
p = PARAM_BY_PLATFORM[PLATFORM]
L, l_f, l_r, m, I_z = p.L, p.l_f, p.l_r, p.m, p.I_z
C_f0, C_r0 = p.C_alpha_f, p.C_alpha_r

SUBSET_FILE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/ford_subset.txt"
csv_paths = [line.strip() for line in open(SUBSET_FILE) if line.strip()]
print(f"Loading {len(csv_paths)} Mach-E segments")

# === Compose: regime-segmentation first, then triage ===
df = segment.load_and_validate(csv_paths)
df = segment.tag(df)
print(f"Total rows: {len(df)}")
print("Regime counts:", df["regime"].value_counts().to_dict())

# Confirm regime mask from triage matches segment.tag regime (lockstep check)
reg_triage = triage.regime_mask(df)
agree = float((reg_triage.values == df["regime"].values).mean())
print(f"Regime-mask lockstep (triage vs segment): agree={agree:.4f}")

def per_regime(resid):
    out = {"overall": triage.rmse(resid)}
    for r in ("straight", "steady", "transient"):
        sub = resid[df["regime"] == r]
        out[r] = triage.rmse(sub) if len(sub) else float("nan")
    return out

results = {}

# ---- V0 baseline (no preprocessing, from existing yaw_rate_resid_rads) ----
resid_v0 = df["yaw_rate_resid_rads"].to_numpy()
results["V0"] = per_regime(resid_v0)
print("V0:", results["V0"])

# ---- V1: KS recalibrated with canonical L + per-segment straight-line bias removal ----
v   = df["v_mps"].to_numpy()
dlt = df["delta_road_rad"].to_numpy()
meas = df["yaw_rate_meas_rads"].to_numpy()
psi_dot_ks = triage.ks_yaw_rate(v, dlt, L)

# bias per segment from straight-line samples (|δ| < 0.01)
df["_pred_v1_raw"] = psi_dot_ks
df["_resid_v1_raw"] = psi_dot_ks - meas
biases = {}
for src, g in df.groupby("__source__"):
    sl = g[np.abs(g["delta_road_rad"]) < 0.01]
    biases[src] = float(sl["_resid_v1_raw"].mean()) if len(sl) else 0.0
bias_arr = df["__source__"].map(biases).to_numpy()
pred_v1 = psi_dot_ks - bias_arr
resid_v1 = pred_v1 - meas
results["V1"] = per_regime(resid_v1)
print("V1:", results["V1"])

# ---- V2: Linear ST with prior Cα ----
pred_v2 = triage.linear_st_yaw_rate(v, dlt, L, l_f, l_r, m, I_z, C_f0, C_r0)
# apply same per-segment straight bias (small)
df["_resid_v2_raw"] = pred_v2 - meas
biases2 = {}
for src, g in df.groupby("__source__"):
    sl = g[np.abs(g["delta_road_rad"]) < 0.01]
    biases2[src] = float(sl["_resid_v2_raw"].mean()) if len(sl) else 0.0
bias2_arr = df["__source__"].map(biases2).to_numpy()
pred_v2 = pred_v2 - bias2_arr
resid_v2 = pred_v2 - meas
results["V2"] = per_regime(resid_v2)
print("V2:", results["V2"])

# ---- V3: Linear ST with fit Cα ----
# triage.fit_c_alpha uses L-BFGS-B at default step which is below numerical
# resolution for params O(1e5); the optimiser returns x0 unchanged. We use a
# coarse-grid + fine-grid search instead. Documented as a limitation; the
# skill's helper is the cause, not a methodology change.
def _fit_c_alpha_grid(df_in):
    vv = df_in["v_mps"].to_numpy(); dd = df_in["delta_road_rad"].to_numpy()
    yy = df_in["yaw_rate_meas_rads"].to_numpy()
    bounds = triage.C_ALPHA_BOUNDS
    def _loss(cf, cr):
        pr = triage.linear_st_yaw_rate(vv, dd, L, l_f, l_r, m, I_z, cf, cr)
        e = pr - yy
        e = e[np.isfinite(e)]
        return float(np.sqrt(np.mean(e**2)))
    g = np.linspace(*bounds, 25)
    best = (1e9, bounds[0], bounds[0])
    for cf_ in g:
        for cr_ in g:
            l = _loss(cf_, cr_)
            if l < best[0]:
                best = (l, cf_, cr_)
    cf0, cr0 = best[1], best[2]
    f1 = np.linspace(max(bounds[0], cf0-5e4), min(bounds[1], cf0+5e4), 40)
    f2 = np.linspace(max(bounds[0], cr0-5e4), min(bounds[1], cr0+5e4), 40)
    for cf_ in f1:
        for cr_ in f2:
            l = _loss(cf_, cr_)
            if l < best[0]:
                best = (l, cf_, cr_)
    pegged_local = (abs(best[1] - bounds[1]) < 1.0) or (abs(best[2] - bounds[1]) < 1.0)
    return float(best[1]), float(best[2]), pegged_local

cf, cr, pegged = _fit_c_alpha_grid(df)
print(f"V3 fit (grid): C_alpha_f={cf:.2f}, C_alpha_r={cr:.2f}, pegged={pegged}")
pred_v3 = triage.linear_st_yaw_rate(v, dlt, L, l_f, l_r, m, I_z, cf, cr)
df["_resid_v3_raw"] = pred_v3 - meas
biases3 = {}
for src, g in df.groupby("__source__"):
    sl = g[np.abs(g["delta_road_rad"]) < 0.01]
    biases3[src] = float(sl["_resid_v3_raw"].mean()) if len(sl) else 0.0
bias3_arr = df["__source__"].map(biases3).to_numpy()
pred_v3 = pred_v3 - bias3_arr
resid_v3 = pred_v3 - meas
results["V3"] = per_regime(resid_v3)
print("V3:", results["V3"])

# ---- V4: residual learner on V3 residuals, LOO ----
# Build a temp df with __source__ + correct residual col
df_v4 = df.copy()
df_v4["_resid_v3"] = resid_v3
# Need a_y_pred_mps2 - check
if "a_y_pred_mps2" not in df_v4.columns:
    df_v4["a_y_pred_mps2"] = 0.0
oof, info = triage.residual_learner_loo(df_v4, residual_col="_resid_v3")
pred_v4 = pred_v3 - oof  # subtract learned residual
resid_v4 = pred_v4 - meas
results["V4"] = per_regime(resid_v4)
print("V4:", results["V4"], "info:", info)

# Save best variant CSV for sensor
best_name = min(results, key=lambda k: results[k]["overall"])
print(f"BEST: {best_name}")
preds = {"V0": meas + resid_v0, "V1": pred_v1, "V2": pred_v2, "V3": pred_v3, "V4": pred_v4}
out_df = df[["t_s", "delta_road_rad", "yaw_rate_meas_rads", "yaw_rate_resid_rads"]].copy()
out_df["yaw_rate_pred_rads"] = preds[best_name]
out_path = ROOT / "out" / f"best_variant_{best_name}.csv"
out_df.to_csv(out_path, index=False)
print(f"Wrote {out_path}")

# Print summary block
import json
print("\n=== RESULTS_JSON ===")
print(json.dumps({k: {kk: (None if (isinstance(vv, float) and (vv != vv)) else vv) for kk, vv in d.items()} for k, d in results.items()}, indent=2))
print(f"=== BEST: {best_name} ===")
print(f"=== FIT: cf={cf:.2f} cr={cr:.2f} pegged={pegged} ===")
print(f"=== V4_OOF_RMSE: {info['oof_rmse']:.6f} ===")
