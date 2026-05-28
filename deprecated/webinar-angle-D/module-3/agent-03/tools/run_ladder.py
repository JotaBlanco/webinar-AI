#!/usr/bin/env python3
"""Run the lateral-fidelity-triage 5-step ladder on Ford Mach-E segments."""
from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "lateral-fidelity-triage"))
sys.path.insert(0, str(ROOT / "code"))

import triage  # noqa: E402
from parameters import PARAM_BY_PLATFORM  # noqa: E402

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
P = PARAM_BY_PLATFORM[PLATFORM]

SEG_DIR = ROOT / "data" / "sim" / "segments" / PLATFORM
# pick the first N segments deterministically
all_csvs = sorted(SEG_DIR.rglob("sim.csv"))
N = 12
csvs = all_csvs[:N]
print(f"Using {len(csvs)} Mach-E segments")

# Load and concatenate
df = triage.load_many(csvs)

# Per-segment yaw-gyro bias on straight-line samples.
# Definition: mean of (meas - pred_variant) where |delta_road| < 0.01.
# For V1+ we want the bias of the *new* prediction; KS and ST both predict ~0
# on straights, so the value is dominated by the measurement offset. Using the
# stock-resid column gives the right value because pred_stock ≈ 0 on straights.
def per_segment_bias(df: pd.DataFrame, residual: np.ndarray) -> np.ndarray:
    b = np.zeros(len(df))
    s = df["delta_road_rad"].abs().to_numpy() < 0.01
    for src, g in df.groupby("__source__"):
        idx = g.index.to_numpy()
        mask_local = s[idx]
        if mask_local.any():
            bval = float(np.mean(residual[idx][mask_local]))
        else:
            bval = 0.0
        b[idx] = bval
    return b

# Use the stock residual column for the canonical bias (skill's recipe).
bias_arr = per_segment_bias(df, df["yaw_rate_resid_rads"].to_numpy())
bias = pd.Series(bias_arr, index=df.index)
meas = df["yaw_rate_meas_rads"].to_numpy()
v = df["v_mps"].to_numpy()
delta = df["delta_road_rad"].to_numpy()

reg = triage.regime_mask(df)

def regimes(resid):
    r = {"overall": triage.rmse(resid)}
    for name in ("straight", "steady", "transient"):
        sub = resid[reg.to_numpy() == name]
        r[name] = triage.rmse(sub) if len(sub) else float("nan")
    return r

# Residual convention in this dataset: yaw_rate_resid = meas - pred
# (verified empirically: max |meas - pred - resid| < 1e-7).
# We use r = meas - pred throughout for clarity.

# V0 — baseline RMSE of existing yaw_rate_resid_rads (no preprocessing)
v0_resid = df["yaw_rate_resid_rads"].to_numpy()
V0 = regimes(v0_resid)

# V1 — KS recalibrated with canonical L + per-segment yaw-gyro bias subtract.
# Bias on straight-line samples is computed from r = meas - pred (i.e. existing resid).
ks_pred = triage.ks_yaw_rate(v, delta, P.L)
r_ks = meas - ks_pred                          # meas - pred convention
v1_resid = r_ks - bias.to_numpy()              # remove per-seg gyro bias
V1 = regimes(v1_resid)

# V2 — Linear ST with prior C_alpha from PARAM_BY_PLATFORM, v_min fallback
st_pred_prior = triage.linear_st_yaw_rate(
    v, delta, P.L, P.l_f, P.l_r, P.m, P.I_z, P.C_alpha_f, P.C_alpha_r,
)
r_st_prior = meas - st_pred_prior
v2_resid = r_st_prior - bias.to_numpy()
V2 = regimes(v2_resid)

# V3 — Fit C_alpha. Note: triage.fit_c_alpha minimises RMSE of pred-meas with
# `pred = linear_st_yaw_rate`, but since RMSE is symmetric in sign, this is fine.
cf, cr, pegged = triage.fit_c_alpha(df, P.L, P.l_f, P.l_r, P.m, P.I_z)
st_pred_fit = triage.linear_st_yaw_rate(
    v, delta, P.L, P.l_f, P.l_r, P.m, P.I_z, cf, cr,
)
r_st_fit = meas - st_pred_fit
v3_resid = r_st_fit - bias.to_numpy()
V3 = regimes(v3_resid)
print(f"Fit C_alpha_f={cf:.0f}  C_alpha_r={cr:.0f}  pegged={pegged}")

# V4 — Residual learner LOO on V3 residuals
df_v3 = df.copy()
df_v3["yaw_rate_resid_v3"] = v3_resid
try:
    oof, info = triage.residual_learner_loo(df_v3, residual_col="yaw_rate_resid_v3")
    v4_resid = v3_resid - oof
    V4 = regimes(v4_resid)
    v4_ok = True
    v4_info = info
except Exception as e:
    print(f"V4 failed: {e}")
    V4 = {"overall": float("nan"), "straight": float("nan"), "steady": float("nan"), "transient": float("nan")}
    v4_ok = False
    v4_info = {}

results = {"V0": V0, "V1": V1, "V2": V2, "V3": V3, "V4": V4}
for k, v_ in results.items():
    print(f"{k}: {v_}")

# Marginal accounting
def marginal(prev, cur):
    return prev["overall"] - cur["overall"]
margins = {
    "V1": marginal(V0, V1),
    "V2": marginal(V1, V2),
    "V3": marginal(V2, V3),
    "V4": marginal(V3, V4) if v4_ok else float("nan"),
}
total = V0["overall"] - (V4["overall"] if v4_ok else V3["overall"])
sum_marg = sum(m for m in margins.values() if np.isfinite(m))
print(f"\nTotal drop V0 -> last: {total:.6f}")
print(f"Sum of marginals: {sum_marg:.6f}")
print(f"Margins: {margins}")

# Decide best variant honestly
best_name = "V0"
best_overall = V0["overall"]
for name, r in [("V1", V1), ("V2", V2), ("V3", V3), ("V4", V4)]:
    if np.isfinite(r["overall"]) and r["overall"] < best_overall:
        best_overall = r["overall"]
        best_name = name
print(f"\nBest variant: {best_name} @ overall RMSE={best_overall:.6f}")

# Write best-variant CSV for sensor
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)
best_pred_map = {
    "V0": df["yaw_rate_pred_rads"].to_numpy(),
    "V1": ks_pred + bias.to_numpy(),
    "V2": st_pred_prior + bias.to_numpy(),
    "V3": st_pred_fit + bias.to_numpy(),
}
if v4_ok:
    # V4 prediction: V3-pred + learned residual correction.
    # Since V4 learns y - oof on r_v3 = meas - pred_v3, the correction adds to pred.
    best_pred_map["V4"] = st_pred_fit + bias.to_numpy() + oof

out_df = pd.DataFrame({
    "yaw_rate_pred_rads": best_pred_map[best_name],
    "yaw_rate_meas_rads": meas,
    "delta_road_rad": delta,
    "yaw_rate_resid_rads": df["yaw_rate_resid_rads"].to_numpy(),
})
best_csv = OUT / f"best_variant_{best_name}.csv"
out_df.to_csv(best_csv, index=False)
print(f"Wrote {best_csv}")

# Print a JSON-ish dump for the report
import json
summary = {
    "platform": PLATFORM,
    "n_segments": len(csvs),
    "n_rows": len(df),
    "results": results,
    "margins": margins,
    "total_drop": total,
    "sum_marg": sum_marg,
    "fit": {"C_alpha_f": cf, "C_alpha_r": cr, "pegged": pegged},
    "v4_ok": v4_ok,
    "v4_info": v4_info,
    "best": best_name,
    "best_overall": best_overall,
    "best_csv": str(best_csv),
}
print("SUMMARY_JSON=" + json.dumps(summary, default=float))
