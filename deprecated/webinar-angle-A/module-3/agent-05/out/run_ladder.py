"""Run lateral-fidelity variant ladder on Ford Mustang Mach-E segments.

V0: baseline (yaw_rate_resid_rads as-is)
V1: KS recalibrated using canonical L from PARAM_BY_PLATFORM (+ per-segment yaw bias)
V2: Linear ST with prior C_alpha
V3: Linear ST with fit C_alpha (bounded)
V4: Residual learner on top of V3 (LOO CV)
"""
from __future__ import annotations
import sys, glob, json
from pathlib import Path
import numpy as np
import pandas as pd

# Allow importing skill helpers and parameters
HERE = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-3/agent-05")
sys.path.insert(0, str(HERE / "skills" / "lateral-fidelity-triage"))
sys.path.insert(0, str(HERE / "code"))

import triage  # noqa: E402
from parameters import PARAM_BY_PLATFORM  # noqa: E402

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
P = PARAM_BY_PLATFORM[PLATFORM]
L, l_f, l_r, m, I_z = P.L, P.l_f, P.l_r, P.m, P.I_z
C_AF_PRIOR, C_AR_PRIOR = P.C_alpha_f, P.C_alpha_r

SEG_GLOB = str(HERE / "data" / "sim" / "segments" / PLATFORM / "*" / "*" / "*" / "sim.csv")
paths = sorted(glob.glob(SEG_GLOB))
print(f"Found {len(paths)} segments for {PLATFORM}", file=sys.stderr)

# Cap to keep runtime reasonable
MAX_SEG = 80
paths = paths[:MAX_SEG]
print(f"Using {len(paths)} segments", file=sys.stderr)

df = triage.load_many(paths)
print(f"Total rows: {len(df):,}", file=sys.stderr)

# Drop non-finite rows in required columns
req = ["v_mps", "delta_road_rad", "yaw_rate_meas_rads", "yaw_rate_pred_rads", "yaw_rate_resid_rads"]
df = df.replace([np.inf, -np.inf], np.nan).dropna(subset=req).reset_index(drop=True)
print(f"After dropna: {len(df):,} rows", file=sys.stderr)

regime = triage.regime_mask(df)

def per_regime(resid: np.ndarray) -> dict:
    out = {"overall": triage.rmse(resid)}
    for r in ("straight", "steady", "transient"):
        mask = (regime == r).to_numpy()
        out[r] = triage.rmse(resid[mask]) if mask.any() else float("nan")
    return out

results = {}

# ---------- V0: baseline (as-is) ----------
v0_resid = df["yaw_rate_resid_rads"].to_numpy()
results["V0_baseline"] = per_regime(v0_resid)

# ---------- V1: KS recalibrated + per-segment yaw bias ----------
v = df["v_mps"].to_numpy()
delta = df["delta_road_rad"].to_numpy()
meas = df["yaw_rate_meas_rads"].to_numpy()

ks_pred = triage.ks_yaw_rate(v, delta, L)
v1_resid_raw = ks_pred - meas

# Per-segment bias: mean residual on straight samples
bias_map = {}
for seg, sub in df.groupby("__source__"):
    idx = sub.index.to_numpy()
    seg_resid_straight = v1_resid_raw[idx][(regime.loc[idx] == "straight").to_numpy()]
    bias_map[seg] = float(np.mean(seg_resid_straight)) if seg_resid_straight.size else 0.0

bias_vec = df["__source__"].map(bias_map).to_numpy()
v1_resid = v1_resid_raw - bias_vec
results["V1_KS_recal"] = per_regime(v1_resid)

# ---------- V2: Linear ST with prior C_alpha ----------
st_prior = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, C_AF_PRIOR, C_AR_PRIOR)
# Also subtract the same per-segment straight-line bias from V1 to keep apples-apples
v2_resid_raw = st_prior - meas
bias_map2 = {}
for seg, sub in df.groupby("__source__"):
    idx = sub.index.to_numpy()
    s = v2_resid_raw[idx][(regime.loc[idx] == "straight").to_numpy()]
    bias_map2[seg] = float(np.mean(s)) if s.size else 0.0
bias2 = df["__source__"].map(bias_map2).to_numpy()
v2_resid = v2_resid_raw - bias2
results["V2_ST_prior"] = per_regime(v2_resid)

# ---------- V3: Linear ST with fit C_alpha ----------
# Skill helper uses L-BFGS-B with default finite-difference step which gives
# numerically-zero gradients for parameter values ~1e5. Re-do the fit with
# Nelder-Mead, which doesn't need gradients, then check the upper-bound peg
# manually.
from scipy.optimize import minimize  # noqa: E402

def _st_loss(params):
    cf_, cr_ = params
    if cf_ < triage.C_ALPHA_BOUNDS[0] or cf_ > triage.C_ALPHA_BOUNDS[1]:
        return 1e6
    if cr_ < triage.C_ALPHA_BOUNDS[0] or cr_ > triage.C_ALPHA_BOUNDS[1]:
        return 1e6
    pred = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, cf_, cr_)
    e = pred - meas
    e = e[np.isfinite(e)]
    return float(np.sqrt(np.mean(e ** 2)))

res = minimize(_st_loss, [C_AF_PRIOR, C_AR_PRIOR], method="Nelder-Mead",
               options={"xatol": 100, "fatol": 1e-7, "maxiter": 1000})
cf, cr = float(res.x[0]), float(res.x[1])
pegged = (abs(cf - triage.C_ALPHA_BOUNDS[1]) < 1.0) or (abs(cr - triage.C_ALPHA_BOUNDS[1]) < 1.0)
print(f"Fit C_alpha_f={cf:.0f}  C_alpha_r={cr:.0f}  pegged={pegged}", file=sys.stderr)
st_fit = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, cf, cr)
v3_resid_raw = st_fit - meas
bias_map3 = {}
for seg, sub in df.groupby("__source__"):
    idx = sub.index.to_numpy()
    s = v3_resid_raw[idx][(regime.loc[idx] == "straight").to_numpy()]
    bias_map3[seg] = float(np.mean(s)) if s.size else 0.0
bias3 = df["__source__"].map(bias_map3).to_numpy()
v3_resid = v3_resid_raw - bias3
results["V3_ST_fit"] = per_regime(v3_resid)

# ---------- V4: Residual learner on V3 residuals (LOO) ----------
# Build feature matrix; targets = V3 residuals
from sklearn.linear_model import Ridge

t = df["t_s"].to_numpy()
dt = np.where(np.diff(t, prepend=t[0]) > 0, np.diff(t, prepend=t[0]), 0.02)
ddelta = np.gradient(delta) / dt
a_y = df["a_y_pred_mps2"].to_numpy() if "a_y_pred_mps2" in df.columns else np.zeros(len(df))
X = np.column_stack([v, np.abs(a_y), np.abs(delta), np.sign(ddelta)])
y_target = v3_resid.copy()  # we want to predict the remaining V3 residual

segs = df["__source__"].unique()
oof = np.full(len(df), np.nan)
for seg in segs:
    train = (df["__source__"] != seg).to_numpy()
    test = ~train
    if train.sum() < 100 or test.sum() < 1:
        oof[test] = 0.0
        continue
    model = Ridge(alpha=1.0).fit(X[train], y_target[train])
    oof[test] = model.predict(X[test])
v4_resid = v3_resid - oof
results["V4_residual_learner"] = per_regime(v4_resid)

# Fit info
fit_info = {
    "platform": PLATFORM,
    "L": L, "l_f": l_f, "l_r": l_r, "m": m, "I_z": I_z,
    "C_alpha_f_prior": C_AF_PRIOR, "C_alpha_r_prior": C_AR_PRIOR,
    "C_alpha_f_fit": cf, "C_alpha_r_fit": cr, "pegged_at_upper": pegged,
    "n_segments_used": len(paths),
    "n_rows": int(len(df)),
    "n_straight": int((regime == "straight").sum()),
    "n_steady": int((regime == "steady").sum()),
    "n_transient": int((regime == "transient").sum()),
}

out_path = HERE / "out" / "ladder_results.json"
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w") as f:
    json.dump({"results": results, "fit_info": fit_info}, f, indent=2)

print(json.dumps({"results": results, "fit_info": fit_info}, indent=2))
