"""Run the lateral-fidelity-triage variant ladder on Mach-E segments."""
from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "skills" / "lateral-fidelity-triage"))
sys.path.insert(0, str(ROOT / "code"))

import triage  # noqa: E402
from parameters import PARAM_BY_PLATFORM  # noqa: E402

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
P = PARAM_BY_PLATFORM[PLATFORM]
L, l_f, l_r, m, I_z = P.L, P.l_f, P.l_r, P.m, P.I_z
C_alpha_f0, C_alpha_r0 = P.C_alpha_f, P.C_alpha_r

# Find sim csvs for Mach-E (limit to keep runtime modest)
seg_root = ROOT / "data" / "sim" / "segments" / PLATFORM
csvs = sorted(seg_root.rglob("sim.csv"))
print(f"found {len(csvs)} sim.csv files for {PLATFORM}", file=sys.stderr)

# Use a manageable subset across devices/routes for diversity
# Take up to 30 segments, spread across the list
N = 30
if len(csvs) > N:
    step = len(csvs) // N
    csvs = csvs[::step][:N]
print(f"using {len(csvs)} segments", file=sys.stderr)

df = triage.load_many(csvs)
print(f"rows: {len(df)}", file=sys.stderr)

reg = triage.regime_mask(df)
df["__regime__"] = reg

def per_regime(resid):
    out = {"overall": triage.rmse(resid)}
    for r in ("straight", "steady", "transient"):
        sel = reg == r
        out[r] = triage.rmse(np.asarray(resid)[sel.to_numpy()]) if sel.any() else float("nan")
    return out

# V0 — baseline, the existing residual column as-is
v0 = df["yaw_rate_resid_rads"].to_numpy()
v0_rmse = per_regime(v0)
print("V0", v0_rmse)

# V1 — KS recalibrated using canonical L + per-segment yaw-gyro bias on straight samples
v1_pred = np.zeros(len(df))
v1_resid = np.zeros(len(df))
for src, sub in df.groupby("__source__"):
    idx = sub.index.to_numpy()
    v = sub["v_mps"].to_numpy()
    delta = sub["delta_road_rad"].to_numpy()
    meas = sub["yaw_rate_meas_rads"].to_numpy()
    pred_ks = triage.ks_yaw_rate(v, delta, L)
    raw_resid = pred_ks - meas
    straight = np.abs(delta) < 0.01
    bias = float(np.nanmean(raw_resid[straight])) if straight.any() else 0.0
    pred_ks_unbiased = pred_ks - bias
    v1_pred[idx] = pred_ks_unbiased
    v1_resid[idx] = pred_ks_unbiased - meas
v1_rmse = per_regime(v1_resid)
print("V1", v1_rmse)

# V2 — Linear ST with prior C_alpha from parameters
v2_pred = triage.linear_st_yaw_rate(
    df["v_mps"].to_numpy(), df["delta_road_rad"].to_numpy(),
    L, l_f, l_r, m, I_z, C_alpha_f0, C_alpha_r0,
)
# Re-apply per-segment bias on straight (consistent with V1 approach: rigid only on bias)
v2_resid = np.zeros(len(df))
for src, sub in df.groupby("__source__"):
    idx = sub.index.to_numpy()
    meas = sub["yaw_rate_meas_rads"].to_numpy()
    pred_local = v2_pred[idx]
    raw = pred_local - meas
    straight = np.abs(sub["delta_road_rad"].to_numpy()) < 0.01
    bias = float(np.nanmean(raw[straight])) if straight.any() else 0.0
    v2_pred[idx] = pred_local - bias
    v2_resid[idx] = pred_local - bias - meas
v2_rmse = per_regime(v2_resid)
print("V2", v2_rmse)

# V3 — Linear ST with fit C_alpha
cf, cr, pegged = triage.fit_c_alpha(df, L, l_f, l_r, m, I_z)
print(f"V3 fit: C_alpha_f={cf:.0f} C_alpha_r={cr:.0f} pegged_at_upper={pegged}")
v3_pred = triage.linear_st_yaw_rate(
    df["v_mps"].to_numpy(), df["delta_road_rad"].to_numpy(),
    L, l_f, l_r, m, I_z, cf, cr,
)
v3_resid = np.zeros(len(df))
for src, sub in df.groupby("__source__"):
    idx = sub.index.to_numpy()
    meas = sub["yaw_rate_meas_rads"].to_numpy()
    pred_local = v3_pred[idx]
    raw = pred_local - meas
    straight = np.abs(sub["delta_road_rad"].to_numpy()) < 0.01
    bias = float(np.nanmean(raw[straight])) if straight.any() else 0.0
    v3_pred[idx] = pred_local - bias
    v3_resid[idx] = pred_local - bias - meas
v3_rmse = per_regime(v3_resid)
print("V3", v3_rmse)

# V4 — residual learner LOO on top of V3 predictions
df_v3 = df.copy()
df_v3["yaw_rate_resid_rads"] = v3_resid  # treat V3 residual as the target
oof, info = triage.residual_learner_loo(df_v3, residual_col="yaw_rate_resid_rads")
v4_pred = v3_pred + oof
v4_resid = v4_pred - df["yaw_rate_meas_rads"].to_numpy()
v4_rmse = per_regime(v4_resid)
print("V4 (oof)", v4_rmse, "info=", info)

# Pick best variant for sensor.py
rows = [
    ("V0", v0_rmse, None),
    ("V1", v1_rmse, v1_pred),
    ("V2", v2_rmse, v2_pred),
    ("V3", v3_rmse, v3_pred),
    ("V4", v4_rmse, v4_pred),
]
best_name, best_rmse, best_pred = min(
    (r for r in rows if r[2] is not None),
    key=lambda r: r[1]["overall"],
)
print(f"BEST: {best_name} overall={best_rmse['overall']:.5f}")

# Write best-variant CSV for sensor.py
out_dir = ROOT / "out"
out_dir.mkdir(exist_ok=True)
best_df = pd.DataFrame({
    "yaw_rate_pred_rads": best_pred,
    "yaw_rate_meas_rads": df["yaw_rate_meas_rads"].to_numpy(),
    "delta_road_rad": df["delta_road_rad"].to_numpy(),
    "yaw_rate_resid_rads": df["yaw_rate_resid_rads"].to_numpy(),  # original V0 column
})
best_csv = out_dir / f"best_variant_{best_name}.csv"
best_df.to_csv(best_csv, index=False)
print(f"wrote {best_csv}")

# Marginal accounting
order = ["V0", "V1", "V2", "V3", "V4"]
overall = {n: r["overall"] for n, r, _ in rows}
margs = []
for i in range(1, len(order)):
    drop = overall[order[i-1]] - overall[order[i]]
    margs.append((order[i], drop))
total_drop = overall["V0"] - overall["V4"]
sum_marg = sum(d for _, d in margs)
print("marginal drops:", margs)
print(f"sum_marginal={sum_marg:.5f} total_drop_V0_to_V4={total_drop:.5f}")

# Also expose per-regime to a file for transcription
summary = {
    "platform": PLATFORM,
    "n_segments": len(csvs),
    "n_rows": int(len(df)),
    "V0": v0_rmse, "V1": v1_rmse, "V2": v2_rmse, "V3": v3_rmse, "V4": v4_rmse,
    "V3_fit": {"C_alpha_f": cf, "C_alpha_r": cr, "pegged": pegged},
    "best": best_name,
    "best_csv": str(best_csv),
    "marginal_drops": margs,
    "total_drop": total_drop,
    "sum_marginal": sum_marg,
}
import json
with open(out_dir / "summary.json", "w") as f:
    json.dump(summary, f, indent=2, default=str)
print("summary.json written")
