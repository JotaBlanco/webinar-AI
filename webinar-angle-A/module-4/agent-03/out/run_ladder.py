"""Run V0..V4 variant ladder on Ford Mach-E segments, writing intermediate CSV."""
from __future__ import annotations
import sys, glob, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-4/agent-03")
sys.path.insert(0, str(ROOT / "skills" / "lateral-fidelity-triage"))
sys.path.insert(0, str(ROOT / "code"))

import triage  # noqa
from parameters import PARAM_BY_PLATFORM  # noqa

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
SEGDIR = ROOT / "data" / "sim" / "segments" / PLATFORM
csvs = sorted(glob.glob(str(SEGDIR / "**" / "sim.csv"), recursive=True))
print(f"Found {len(csvs)} {PLATFORM} sim.csv files")

df = triage.load_many(csvs)
print("Total rows:", len(df))

# Regime mask per-segment (so gradient is correct per segment)
def regime_per_segment(df):
    out_parts = []
    for src, sub in df.groupby("__source__", sort=False):
        out_parts.append(triage.regime_mask(sub.reset_index(drop=True)).values)
    return np.concatenate(out_parts)

# Rebuild df with consistent per-segment index for regime + ddelta
parts = []
for src, sub in df.groupby("__source__", sort=False):
    s = sub.reset_index(drop=True).copy()
    t = s["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    dt = np.where(dt <= 0, 0.02, dt)
    s["dt"] = dt
    s["ddelta"] = np.gradient(s["delta_road_rad"].to_numpy()) / dt
    s["regime"] = triage.regime_mask(s).values
    parts.append(s)
df = pd.concat(parts, ignore_index=True)

P = PARAM_BY_PLATFORM[PLATFORM]
print(f"Params: L={P.L} m={P.m} l_f={P.l_f} l_r={P.l_r} Cf={P.C_alpha_f} Cr={P.C_alpha_r}")

meas = df["yaw_rate_meas_rads"].to_numpy()
v = df["v_mps"].to_numpy()
delta = df["delta_road_rad"].to_numpy()

# Sign sanity check
straight = df["regime"] == "straight"
cornering = ~straight
corr = np.corrcoef(delta[cornering], meas[cornering])[0,1]
print(f"corr(delta_road, yaw_meas) on cornering = {corr:+.3f}")

def rmse(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float(np.sqrt(np.mean(x**2))) if x.size else float("nan")

def per_regime(resid):
    out = {"overall": rmse(resid)}
    for r in ("straight","steady","transient"):
        m = (df["regime"]==r).values
        out[r] = rmse(resid[m])
    return out

# V0 — baseline: use yaw_rate_resid_rads as-is
v0_resid = df["yaw_rate_resid_rads"].to_numpy()
V0 = per_regime(v0_resid)
print("V0:", V0)

# V1 — KS recalibrated with PARAM L (already L for the platform is in the CSV builder?)
#   re-compute KS yaw rate with canonical L, then subtract per-segment yaw-gyro bias
ks_pred = triage.ks_yaw_rate(v, delta, P.L)
v1_resid_raw = ks_pred - meas
# Per-segment bias on straight samples
bias = np.zeros(len(df))
for src, sub in df.groupby("__source__", sort=False):
    m = (sub["regime"].values == "straight")
    idx = sub.index.values
    if m.sum() > 10:
        b = np.nanmean((ks_pred[idx][m] - meas[idx][m]))
    else:
        b = 0.0
    bias[idx] = b
v1_resid = v1_resid_raw - bias
V1 = per_regime(v1_resid)
print("V1:", V1)

# V2 — Linear ST with prior C_α
st_pred_prior = triage.linear_st_yaw_rate(v, delta, P.L, P.l_f, P.l_r, P.m, P.I_z,
                                          P.C_alpha_f, P.C_alpha_r)
# Apply same per-segment bias correction (fair comparison – same DOF as V1)
v2_resid_raw = st_pred_prior - meas
bias_v2 = np.zeros(len(df))
for src, sub in df.groupby("__source__", sort=False):
    m = (sub["regime"].values == "straight")
    idx = sub.index.values
    if m.sum() > 10:
        b = np.nanmean(st_pred_prior[idx][m] - meas[idx][m])
    else:
        b = 0.0
    bias_v2[idx] = b
v2_resid = v2_resid_raw - bias_v2
V2 = per_regime(v2_resid)
print("V2:", V2)

# V3 — Linear ST with fitted C_α (joint fit on all segments after applying bias)
from scipy.optimize import differential_evolution
regime_vals = df["regime"].values
seg_idxs = []
for src, sub in df.groupby("__source__", sort=False):
    idx = sub.index.values
    m = regime_vals[idx] == "straight"
    seg_idxs.append((idx, idx[m] if m.sum() > 10 else None))

def loss(params):
    cf, cr = params
    pred = triage.linear_st_yaw_rate(v, delta, P.L, P.l_f, P.l_r, P.m, P.I_z, cf, cr)
    e = pred - meas
    for idx, m_idx in seg_idxs:
        if m_idx is None: continue
        b = float(np.nanmean(e[m_idx]))
        e[idx] -= b
    e = e[np.isfinite(e)]
    return float(np.sqrt(np.mean(e**2)))

bounds = [(5e4, 5e5), (5e4, 5e5)]
res = differential_evolution(loss, bounds, seed=42, tol=1e-6, maxiter=60, popsize=15, workers=1)
cf_fit, cr_fit = float(res.x[0]), float(res.x[1])
pegged = (abs(cf_fit-5e5) < 100) or (abs(cr_fit-5e5) < 100) or (abs(cf_fit-5e4)<100) or (abs(cr_fit-5e4)<100)
print(f"Fit Cf={cf_fit:.0f} Cr={cr_fit:.0f} pegged={pegged}")
st_pred_fit = triage.linear_st_yaw_rate(v, delta, P.L, P.l_f, P.l_r, P.m, P.I_z, cf_fit, cr_fit)
v3_resid_raw = st_pred_fit - meas
b_v3 = np.zeros(len(df))
for src, sub in df.groupby("__source__", sort=False):
    m = (sub["regime"].values == "straight")
    idx = sub.index.values
    if m.sum() > 10:
        b_v3[idx] = np.nanmean(st_pred_fit[idx][m] - meas[idx][m])
v3_resid = v3_resid_raw - b_v3
V3 = per_regime(v3_resid)
print("V3:", V3)

# V4 — Residual learner on V3 residuals (LOO-CV)
from sklearn.linear_model import Ridge
segs = df["__source__"].unique()
ddelta = df["ddelta"].to_numpy()
a_y = df["a_y_pred_mps2"].to_numpy() if "a_y_pred_mps2" in df.columns else np.zeros(len(df))
X = np.column_stack([v, np.abs(a_y), np.abs(delta), np.sign(ddelta)])
y = v3_resid.copy()  # learner predicts the V3 residual
oof = np.full(len(df), np.nan)
src_arr = df["__source__"].values
if len(segs) >= 2:
    for seg in segs:
        train = src_arr != seg
        test = ~train
        model = Ridge(alpha=1.0).fit(X[train], y[train])
        oof[test] = model.predict(X[test])
    v4_resid = v3_resid - oof
else:
    v4_resid = v3_resid.copy()
V4 = per_regime(v4_resid)
print("V4:", V4)

results = {"V0":V0,"V1":V1,"V2":V2,"V3":V3,"V4":V4,
           "n_segments": int(len(segs)),
           "n_rows": int(len(df)),
           "params": {"L":P.L,"m":P.m,"l_f":P.l_f,"l_r":P.l_r,
                      "C_alpha_f_prior":P.C_alpha_f,"C_alpha_r_prior":P.C_alpha_r,
                      "C_alpha_f_fit":cf_fit,"C_alpha_r_fit":cr_fit,
                      "pegged": bool(pegged)},
           "sign_corr_cornering": float(corr)}
outp = ROOT / "out" / "ladder_results.json"
outp.write_text(json.dumps(results, indent=2))
print("Wrote", outp)
