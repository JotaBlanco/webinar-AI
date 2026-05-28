"""Run the lateral-fidelity variant ladder on Ford Mach-E segments.

V0  baseline (yaw_rate_resid_rads as-is)
V1  KS recalibrated + per-segment yaw-gyro bias on straight samples
V2  Linear ST with prior C_alpha
V3  Linear ST with fit C_alpha (global)
V4  Ridge residual learner on V3 residuals, LOSO CV
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
AGENT_DIR = HERE.parent
sys.path.insert(0, str(AGENT_DIR / "skills" / "lateral-fidelity-triage"))
sys.path.insert(0, str(AGENT_DIR / "code"))

import triage  # type: ignore
from parameters import PARAM_BY_PLATFORM  # type: ignore

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
P = PARAM_BY_PLATFORM[PLATFORM]

DATA_ROOT = AGENT_DIR / "data" / "sim" / "segments" / PLATFORM
OUT = AGENT_DIR / "out"
OUT.mkdir(exist_ok=True)

# Cap segments for time budget — first N
MAX_SEGMENTS = 60

csvs = sorted(DATA_ROOT.rglob("sim.csv"))[:MAX_SEGMENTS]
print(f"Loading {len(csvs)} segments from {PLATFORM}")

df = triage.load_many(csvs)
print(f"Total rows: {len(df)}")

# Regime mask (held constant across all rows / variants)
reg = triage.regime_mask(df)
df["__regime__"] = reg.values

def per_regime_rmse_arr(resid):
    out = {"overall": triage.rmse(resid)}
    for r in ("straight", "steady", "transient"):
        m = df["__regime__"].to_numpy() == r
        out[r] = triage.rmse(resid[m]) if m.sum() else float("nan")
    return out

v = df["v_mps"].to_numpy()
delta = df["delta_road_rad"].to_numpy()
meas = df["yaw_rate_meas_rads"].to_numpy()

# --- V0: as-is baseline
resid_v0 = df["yaw_rate_resid_rads"].to_numpy()
rmse_v0 = per_regime_rmse_arr(resid_v0)

# --- V1: KS recalibrated with canonical L + per-segment yaw-gyro bias on straight
ks_pred = triage.ks_yaw_rate(v, delta, P.L)
resid_v1_raw = ks_pred - meas

# subtract per-segment bias on straight samples
src = df["__source__"].to_numpy()
reg_arr = df["__regime__"].to_numpy()
bias_map = {}
for seg in np.unique(src):
    mseg = (src == seg) & (reg_arr == "straight")
    if mseg.sum() >= 20:
        bias_map[seg] = float(np.nanmean(resid_v1_raw[mseg]))
    else:
        bias_map[seg] = 0.0
bias_per_row = np.array([bias_map[s] for s in src])
resid_v1 = resid_v1_raw - bias_per_row
rmse_v1 = per_regime_rmse_arr(resid_v1)

# --- V2: Linear ST with prior C_alpha
st_pred = triage.linear_st_yaw_rate(
    v, delta, P.L, P.l_f, P.l_r, P.m, P.I_z, P.C_alpha_f, P.C_alpha_r
)
resid_v2_raw = st_pred - meas
# keep same bias model for fairness — subtract per-segment straight bias
bias_map2 = {}
for seg in np.unique(src):
    mseg = (src == seg) & (reg_arr == "straight")
    if mseg.sum() >= 20:
        bias_map2[seg] = float(np.nanmean(resid_v2_raw[mseg]))
    else:
        bias_map2[seg] = 0.0
bias_per_row2 = np.array([bias_map2[s] for s in src])
resid_v2 = resid_v2_raw - bias_per_row2
rmse_v2 = per_regime_rmse_arr(resid_v2)

# --- V3: Linear ST with fit C_alpha
# triage.fit_c_alpha uses L-BFGS-B which gets stuck on flat gradient;
# use grid + Nelder-Mead refinement to find the actual minimum.
from scipy.optimize import minimize as _minimize
def _loss(p):
    cf_, cr_ = p
    pr = triage.linear_st_yaw_rate(v, delta, P.L, P.l_f, P.l_r, P.m, P.I_z, cf_, cr_)
    e = pr - meas
    e = e[np.isfinite(e)]
    return float(np.sqrt(np.mean(e**2)))
best = (1e9, (1.5e5, 1.5e5))
for cf_g in np.linspace(5e4, 5e5, 25):
    for cr_g in np.linspace(5e4, 5e5, 25):
        l = _loss((cf_g, cr_g))
        if l < best[0]:
            best = (l, (cf_g, cr_g))
res = _minimize(_loss, list(best[1]), method="Nelder-Mead", bounds=[(5e4, 5e5), (5e4, 5e5)])
cf, cr = float(res.x[0]), float(res.x[1])
pegged = (abs(cf - 5e5) < 1e3) or (abs(cr - 5e5) < 1e3)
print(f"Fit C_alpha (grid+NM): cf={cf:.0f} cr={cr:.0f} pegged={pegged}")
st_fit_pred = triage.linear_st_yaw_rate(
    v, delta, P.L, P.l_f, P.l_r, P.m, P.I_z, cf, cr
)
resid_v3_raw = st_fit_pred - meas
bias_map3 = {}
for seg in np.unique(src):
    mseg = (src == seg) & (reg_arr == "straight")
    if mseg.sum() >= 20:
        bias_map3[seg] = float(np.nanmean(resid_v3_raw[mseg]))
    else:
        bias_map3[seg] = 0.0
bias_per_row3 = np.array([bias_map3[s] for s in src])
resid_v3 = resid_v3_raw - bias_per_row3
rmse_v3 = per_regime_rmse_arr(resid_v3)

# --- V4: residual learner on V3 residuals, LOSO CV
# Build features manually so we use the V3 residual as target
from sklearn.linear_model import Ridge
t = df["t_s"].to_numpy()
dt = np.where(np.diff(t, prepend=t[0]) > 0, np.diff(t, prepend=t[0]), 0.02)
ddelta = np.gradient(delta) / dt
a_y_pred = df["a_y_pred_mps2"].to_numpy() if "a_y_pred_mps2" in df.columns else np.zeros(len(df))
X = np.column_stack([v, np.abs(a_y_pred), np.abs(delta), np.sign(ddelta)])
y3 = resid_v3
segs = df["__source__"].unique()
oof = np.full(len(df), np.nan)
for seg in segs:
    train = src != seg
    test = ~train
    if train.sum() < 100 or test.sum() < 10:
        oof[test] = 0.0
        continue
    Xt = X[train]
    yt = y3[train]
    mask = np.isfinite(yt) & np.all(np.isfinite(Xt), axis=1)
    if mask.sum() < 50:
        oof[test] = 0.0
        continue
    model = Ridge(alpha=1.0).fit(Xt[mask], yt[mask])
    oof[test] = model.predict(X[test])
resid_v4 = y3 - oof
rmse_v4 = per_regime_rmse_arr(resid_v4)

# Output
results = {
    "platform": PLATFORM,
    "n_segments": len(csvs),
    "n_rows": int(len(df)),
    "regime_counts": {r: int((df["__regime__"] == r).sum()) for r in ("straight", "steady", "transient")},
    "fit_c_alpha": {"cf": cf, "cr": cr, "pegged_at_upper_bound": bool(pegged)},
    "V0": rmse_v0,
    "V1": rmse_v1,
    "V2": rmse_v2,
    "V3": rmse_v3,
    "V4": rmse_v4,
}
print(json.dumps(results, indent=2))
(OUT / "ladder_results.json").write_text(json.dumps(results, indent=2))
print(f"\nWrote {OUT / 'ladder_results.json'}")
