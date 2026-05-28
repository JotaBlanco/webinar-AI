#!/usr/bin/env python3
"""Run the lateral-fidelity-triage ladder composed with regime-segmentation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

AGENT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AGENT_ROOT / "skills" / "lateral-fidelity-triage"))
sys.path.insert(0, str(AGENT_ROOT / "skills" / "regime-segmentation"))
sys.path.insert(0, str(AGENT_ROOT / "code"))

import segment   # regime-segmentation
import triage    # lateral-fidelity-triage
from parameters import PARAM_BY_PLATFORM


PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
DATA_ROOT = AGENT_ROOT / "data" / "sim" / "segments" / PLATFORM

# Pick one segment per route for diversity → LOO over routes.
routes = sorted({p.parent.parent.name for p in DATA_ROOT.rglob("sim.csv")})
csv_paths = []
seen_routes = set()
for csv in sorted(DATA_ROOT.rglob("sim.csv")):
    route = csv.parent.parent.name
    if route in seen_routes:
        continue
    seen_routes.add(route)
    csv_paths.append(csv)
    if len(csv_paths) >= 8:
        break

print(f"Selected {len(csv_paths)} segments (distinct routes):")
for p in csv_paths:
    print(" ", p.relative_to(AGENT_ROOT))

# Step: load + tag regimes
df = segment.load_and_validate([str(p) for p in csv_paths])
df = segment.tag(df)
print(f"Total rows: {len(df)}; regime counts:\n{df['regime'].value_counts()}")

p = PARAM_BY_PLATFORM[PLATFORM]
L, l_f, l_r, m, I_z = p.L, p.l_f, p.l_r, p.m, p.I_z
print(f"Platform={PLATFORM}: L={L}, l_f={l_f}, l_r={l_r}, m={m}, I_z={I_z}, "
      f"C_alpha_f={p.C_alpha_f}, C_alpha_r={p.C_alpha_r}")


def per_regime(series_resid: pd.Series) -> dict[str, float]:
    out = {}
    s = series_resid.to_numpy()
    finite = np.isfinite(s)
    out["overall"] = float(np.sqrt(np.mean(s[finite] ** 2))) if finite.any() else float("nan")
    for r in ("straight", "steady", "transient"):
        m_ = (df["regime"] == r).to_numpy() & finite
        out[r] = float(np.sqrt(np.mean(s[m_] ** 2))) if m_.any() else float("nan")
    return out


results = {}

# V0 — as-is residual
v0_resid = df["yaw_rate_resid_rads"]
results["V0"] = per_regime(v0_resid)

# V1 — KS recalibrated (canonical L) + per-segment yaw-gyro bias on straight-line samples
v = df["v_mps"].to_numpy()
delta = df["delta_road_rad"].to_numpy()
meas = df["yaw_rate_meas_rads"].to_numpy()
ks_pred = triage.ks_yaw_rate(v, delta, L)
v1_resid = ks_pred - meas
# per-segment bias on |δ| < 0.01
bias = np.zeros_like(v1_resid)
for src in df["__source__"].unique():
    mask = (df["__source__"] == src).to_numpy()
    straight_mask = mask & (np.abs(delta) < 0.01)
    if straight_mask.sum() > 0:
        b = float(np.nanmean(v1_resid[straight_mask]))
        bias[mask] = b
v1_resid_corrected = v1_resid - bias
df["v1_pred"] = ks_pred - bias
df["v1_resid"] = v1_resid_corrected
results["V1"] = per_regime(pd.Series(v1_resid_corrected))

# V2 — linear ST with prior C_alpha
v2_pred = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z,
                                    p.C_alpha_f, p.C_alpha_r)
# apply the same V1 bias correction so we don't mix in a gyro-zero error
v2_pred_corr = v2_pred - bias
v2_resid = v2_pred_corr - meas
df["v2_pred"] = v2_pred_corr
df["v2_resid"] = v2_resid
results["V2"] = per_regime(pd.Series(v2_resid))

# V3 — linear ST with fitted C_alpha
cf_fit, cr_fit, pegged = triage.fit_c_alpha(df, L, l_f, l_r, m, I_z)
print(f"Fitted C_alpha_f={cf_fit:.0f}, C_alpha_r={cr_fit:.0f}, pegged={pegged}")
v3_pred = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, cf_fit, cr_fit)
v3_pred_corr = v3_pred - bias
v3_resid = v3_pred_corr - meas
df["v3_pred"] = v3_pred_corr
df["v3_resid"] = v3_resid
results["V3"] = per_regime(pd.Series(v3_resid))

# V4 — residual learner LOO on V3 residuals
df_for_learn = df.copy()
df_for_learn["yaw_rate_resid_rads"] = v3_resid  # learner residual column override
oof, info = triage.residual_learner_loo(df_for_learn, residual_col="yaw_rate_resid_rads")
v4_pred = v3_pred_corr - oof  # subtract learned bias from V3 prediction
v4_resid = v4_pred - meas
df["v4_pred"] = v4_pred
df["v4_resid"] = v4_resid
results["V4"] = per_regime(pd.Series(v4_resid))
print(f"V4 learner OOF RMSE on V3 residual: {info['oof_rmse']:.5f}")

# Print results
print("\n=== Per-regime RMSE ===")
for k, v_ in results.items():
    print(f"{k}: {v_}")

# Marginal accounting
v0_o = results["V0"]["overall"]
for stage in ["V1", "V2", "V3", "V4"]:
    prev = list(results.keys())[list(results.keys()).index(stage)-1]
    drop = results[prev]["overall"] - results[stage]["overall"]
    print(f"marginal {prev}->{stage}: {drop:+.5f}")

# Save best variant CSV (we pick V4 if it actually wins; otherwise V3 etc.)
order = ["V0", "V1", "V2", "V3", "V4"]
best = min(order, key=lambda k: results[k]["overall"])
print(f"Best: {best}")

# Write a best CSV for the sensor (always export the best one's pred + meas + delta + V0 resid)
pred_col_map = {
    "V0": df["yaw_rate_pred_rads"].to_numpy(),
    "V1": df["v1_pred"].to_numpy(),
    "V2": df["v2_pred"].to_numpy(),
    "V3": df["v3_pred"].to_numpy(),
    "V4": df["v4_pred"].to_numpy(),
}
best_pred = pred_col_map[best]

out_dir = AGENT_ROOT / "out"
out_dir.mkdir(exist_ok=True)
best_csv = out_dir / f"best_{best}.csv"
pd.DataFrame({
    "yaw_rate_pred_rads": best_pred,
    "yaw_rate_meas_rads": meas,
    "delta_road_rad": delta,
    "yaw_rate_resid_rads": df["yaw_rate_resid_rads"].to_numpy(),
}).to_csv(best_csv, index=False)
print(f"Wrote {best_csv}")

# Persist results json
(out_dir / "ladder_results.json").write_text(json.dumps({
    "platform": PLATFORM,
    "segments": [str(p) for p in csv_paths],
    "results": results,
    "cf_fit": cf_fit, "cr_fit": cr_fit, "pegged": pegged,
    "v4_oof_rmse_on_v3_resid": info["oof_rmse"],
    "best": best,
}, indent=2))
print(f"Wrote {out_dir/'ladder_results.json'}")
