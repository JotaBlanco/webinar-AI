"""Run the lateral-fidelity-triage variant ladder V0..V4 on Mach-E segments.

Writes per-variant residual CSVs (small summary stats) under out/ and prints
a JSON blob with per-regime RMSEs and attribution deltas.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-2/agent-05")
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "skills" / "lateral-fidelity-triage"))

import triage  # noqa: E402
from parameters import PARAM_BY_PLATFORM  # noqa: E402

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
PARAMS = PARAM_BY_PLATFORM[PLATFORM]

SEG_ROOT = ROOT / "data" / "sim" / "segments" / PLATFORM
# Use a manageable, deterministic subset (sorted) for ~15 min runtime
SEG_PATHS = sorted(SEG_ROOT.rglob("sim.csv"))
N_SEG = 20  # small enough to be fast, large enough for stable per-regime stats
SEG_PATHS = SEG_PATHS[:N_SEG]
print(f"# using {len(SEG_PATHS)} Mach-E sim.csv segments", file=sys.stderr)

df = triage.load_many(SEG_PATHS)
print(f"# combined rows: {len(df)}", file=sys.stderr)

# Quick sign-check on a cornering subset
corner = df[np.abs(df["delta_road_rad"]) > 0.02]
if len(corner) > 100:
    c = float(np.corrcoef(corner["delta_road_rad"], corner["yaw_rate_meas_rads"])[0, 1])
    print(f"# sign check corr(delta, yaw_meas) on cornering: {c:.3f}", file=sys.stderr)

reg = triage.regime_mask(df)

def per_regime(resid: np.ndarray) -> dict:
    r = pd.Series(resid, index=df.index)
    out = {"overall": triage.rmse(r)}
    for k in ("straight", "steady", "transient"):
        sub = r[reg == k]
        out[k] = triage.rmse(sub) if len(sub) else float("nan")
    return out

results = {}

# ---- V0: baseline residual (as shipped in sim.csv) ----
resid_v0 = df["yaw_rate_resid_rads"].to_numpy()
results["V0_baseline"] = per_regime(resid_v0)

# ---- V1: KS recalibrated with canonical L + per-segment straight-line bias ----
v = df["v_mps"].to_numpy()
delta = df["delta_road_rad"].to_numpy()
meas = df["yaw_rate_meas_rads"].to_numpy()

ks_pred = triage.ks_yaw_rate(v, delta, PARAMS.L)
resid_ks = ks_pred - meas

# per-segment straight-line bias subtraction
straight = np.abs(delta) < 0.01
resid_v1 = resid_ks.copy()
for src, sub in df.groupby("__source__"):
    idx = sub.index.to_numpy()
    s_idx = idx[straight[idx]]
    if len(s_idx) > 5:
        bias = float(np.nanmean(resid_ks[s_idx]))
    else:
        bias = 0.0
    resid_v1[idx] = resid_ks[idx] - bias

results["V1_ks_recal"] = per_regime(resid_v1)

# ---- V2: Linear ST with prior C_alpha ----
st_prior = triage.linear_st_yaw_rate(
    v, delta,
    L=PARAMS.L, l_f=PARAMS.l_f, l_r=PARAMS.l_r,
    m=PARAMS.m, I_z=PARAMS.I_z,
    C_alpha_f=PARAMS.C_alpha_f, C_alpha_r=PARAMS.C_alpha_r,
)
resid_v2_raw = st_prior - meas
# apply same per-segment straight bias treatment
resid_v2 = resid_v2_raw.copy()
for src, sub in df.groupby("__source__"):
    idx = sub.index.to_numpy()
    s_idx = idx[straight[idx]]
    bias = float(np.nanmean(resid_v2_raw[s_idx])) if len(s_idx) > 5 else 0.0
    resid_v2[idx] = resid_v2_raw[idx] - bias
results["V2_linear_st_prior"] = per_regime(resid_v2)

# ---- V3: Linear ST with fit C_alpha ----
# Note: triage.fit_c_alpha uses a single L-BFGS-B start at x0=(1.5e5,1.5e5)
# and gets stuck in a non-convex landscape with K_us-singularity cliffs.
# We supplement with a multi-start to find a representative global minimum.
from scipy.optimize import minimize  # noqa: E402
def _loss(params):
    cf, cr = params
    pred = triage.linear_st_yaw_rate(v, delta, PARAMS.L, PARAMS.l_f, PARAMS.l_r,
                                     PARAMS.m, PARAMS.I_z, cf, cr)
    e = pred - meas
    e = e[np.isfinite(e)]
    return float(np.sqrt(np.mean(e**2))) if e.size else float("inf")

best = (None, float("inf"))
for cf0 in (8e4, 1.5e5, 2e5, 3e5, 4e5):
    for cr0 in (8e4, 1.5e5, 2e5, 3e5, 4e5):
        r = minimize(_loss, [cf0, cr0], method="L-BFGS-B",
                     bounds=[triage.C_ALPHA_BOUNDS, triage.C_ALPHA_BOUNDS])
        if r.fun < best[1]:
            best = ((float(r.x[0]), float(r.x[1])), float(r.fun))
cf_fit, cr_fit = best[0]
pegged = (abs(cf_fit - triage.C_ALPHA_BOUNDS[1]) < 1.0
          or abs(cr_fit - triage.C_ALPHA_BOUNDS[1]) < 1.0)
# Reference: helper's single-start result, for comparison
cf_single, cr_single, _ = triage.fit_c_alpha(
    df, L=PARAMS.L, l_f=PARAMS.l_f, l_r=PARAMS.l_r, m=PARAMS.m, I_z=PARAMS.I_z,
)
print(f"# fit C_alpha_f={cf_fit:.1f} N/rad, C_alpha_r={cr_fit:.1f} N/rad, pegged={pegged}",
      file=sys.stderr)

st_fit = triage.linear_st_yaw_rate(
    v, delta,
    L=PARAMS.L, l_f=PARAMS.l_f, l_r=PARAMS.l_r,
    m=PARAMS.m, I_z=PARAMS.I_z,
    C_alpha_f=cf_fit, C_alpha_r=cr_fit,
)
resid_v3_raw = st_fit - meas
resid_v3 = resid_v3_raw.copy()
for src, sub in df.groupby("__source__"):
    idx = sub.index.to_numpy()
    s_idx = idx[straight[idx]]
    bias = float(np.nanmean(resid_v3_raw[s_idx])) if len(s_idx) > 5 else 0.0
    resid_v3[idx] = resid_v3_raw[idx] - bias
results["V3_linear_st_fit"] = per_regime(resid_v3)

# ---- V4: residual learner on top of V3 (LOO over segments) ----
df_v4 = df.copy()
df_v4["yaw_rate_resid_v3"] = resid_v3
oof, info = triage.residual_learner_loo(df_v4, residual_col="yaw_rate_resid_v3")
resid_v4 = resid_v3 - oof
results["V4_residual_learner"] = per_regime(resid_v4)
results["V4_residual_learner"]["oof_rmse_learner_only"] = info["oof_rmse"]

# ---- Attribution: delta in overall RMSE per step ----
order = ["V0_baseline", "V1_ks_recal", "V2_linear_st_prior",
         "V3_linear_st_fit", "V4_residual_learner"]
attribution = {}
prev = results["V0_baseline"]["overall"]
for k in order[1:]:
    cur = results[k]["overall"]
    attribution[k] = {"delta_rmse": cur - prev, "pct_vs_prev": (cur - prev) / prev * 100.0}
    prev = cur

# Total improvement vs V0
total = {
    "rmse_v0": results["V0_baseline"]["overall"],
    "rmse_v4": results["V4_residual_learner"]["overall"],
    "improvement_abs": results["V0_baseline"]["overall"] - results["V4_residual_learner"]["overall"],
    "improvement_pct": (results["V0_baseline"]["overall"] - results["V4_residual_learner"]["overall"])
                        / results["V0_baseline"]["overall"] * 100.0,
}

# Save tiny summary CSV
out_dir = ROOT / "out"
out_dir.mkdir(exist_ok=True)
rows = []
for k in order:
    row = {"variant": k, **results[k]}
    rows.append(row)
pd.DataFrame(rows).to_csv(out_dir / "variant_ladder.csv", index=False)

print(json.dumps({
    "platform": PLATFORM,
    "n_segments": len(SEG_PATHS),
    "n_rows": int(len(df)),
    "c_alpha_fit": {
        "C_alpha_f": cf_fit, "C_alpha_r": cr_fit, "pegged": bool(pegged),
        "single_start_C_alpha_f": cf_single, "single_start_C_alpha_r": cr_single,
    },
    "results": results,
    "attribution": attribution,
    "total": total,
}, indent=2))
