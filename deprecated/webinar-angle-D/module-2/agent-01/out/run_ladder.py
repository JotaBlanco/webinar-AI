"""Run the V0→V4 lateral-fidelity ladder on Ford Mach-E segments."""
from __future__ import annotations
import sys, glob, json
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
MODROOT = HERE.parent
SKILL_DIR = MODROOT / "skills" / "lateral-fidelity-triage"
sys.path.insert(0, str(SKILL_DIR))
sys.path.insert(0, str(MODROOT / "code"))

import triage as T  # noqa: E402
from parameters import MACH_E  # noqa: E402

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
SEG_ROOT = MODROOT / "data" / "sim" / "segments" / PLATFORM

# pick a manageable sample: random/fixed across devices
all_csvs = sorted(glob.glob(str(SEG_ROOT / "*" / "*" / "*" / "sim.csv")))
print(f"found {len(all_csvs)} Mach-E sim CSVs")

# Use ~20 segments (deterministic stride) for tractable run
N_SEG = 20
stride = max(1, len(all_csvs) // N_SEG)
csv_paths = all_csvs[::stride][:N_SEG]
print(f"using {len(csv_paths)} segments (stride={stride})")

df = T.load_many(csv_paths)
print(f"total rows: {len(df)}")

p = MACH_E
L, l_f, l_r, m, I_z = p.L, p.l_f, p.l_r, p.m, p.I_z
CAF0, CAR0 = p.C_alpha_f, p.C_alpha_r

# ----- V0: baseline residual already in CSV
v0_resid = df["yaw_rate_resid_rads"].to_numpy()

# ----- V1: KS recalibrated with canonical L + per-segment bias correction on straights
v = df["v_mps"].to_numpy()
delta = df["delta_road_rad"].to_numpy()
meas = df["yaw_rate_meas_rads"].to_numpy()
ks_pred = T.ks_yaw_rate(v, delta, L)
v1_resid = ks_pred - meas
# subtract straight-line bias per segment
bias_corr = np.zeros_like(v1_resid)
for seg, sub in df.groupby("__source__"):
    idx = sub.index.to_numpy()
    d_sub = delta[idx]
    mask = np.abs(d_sub) < 0.01
    if mask.sum() > 5:
        b = np.nanmean(v1_resid[idx][mask])
    else:
        b = 0.0
    bias_corr[idx] = b
v1_resid_corr = v1_resid - bias_corr

# ----- V2: linear ST with prior C_alpha
st_pred_prior = T.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, CAF0, CAR0)
v2_resid = st_pred_prior - meas
# apply same per-segment straight bias removal
bias_corr2 = np.zeros_like(v2_resid)
for seg, sub in df.groupby("__source__"):
    idx = sub.index.to_numpy()
    d_sub = delta[idx]
    mask = np.abs(d_sub) < 0.01
    if mask.sum() > 5:
        b = np.nanmean(v2_resid[idx][mask])
    else:
        b = 0.0
    bias_corr2[idx] = b
v2_resid_corr = v2_resid - bias_corr2

# ----- V3: fit C_alpha to data  (skill v0.1 helper uses L-BFGS-B and gets stuck at x0
# because the linear-ST loss has a singular ridge where 1 + K_us·v² → 0. We add a
# grid pre-search + Nelder-Mead refine to actually find the minimum.)
caf_fit_skill, car_fit_skill, pegged_skill = T.fit_c_alpha(df, L, l_f, l_r, m, I_z)
print(f"V3 skill-fit: C_alpha_f={caf_fit_skill:.0f}  C_alpha_r={car_fit_skill:.0f}  pegged={pegged_skill}")

from scipy.optimize import minimize as _minimize
def _loss(params):
    cf, cr = params
    if cf <= 0 or cr <= 0: return 1e9
    pred = T.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, cf, cr)
    e = pred - meas
    e = e[np.isfinite(e)]
    return float(np.sqrt(np.mean(e**2))) if e.size else 1e9
# coarse grid in log-space, restricted to upper-Cα regime where understeer is positive
grid = np.geomspace(1.0e5, 1.0e6, 12)
best = (np.inf, None)
for cf in grid:
    for cr in grid:
        K_us = (m*(l_r*cr - l_f*cf)) / (L**2 * cf * cr)
        if 1 + K_us * 35**2 <= 0:  # avoid singular regime
            continue
        L_ = _loss((cf, cr))
        if L_ < best[0]:
            best = (L_, (cf, cr))
x0 = list(best[1])
res = _minimize(_loss, x0, method="Nelder-Mead",
                options={"xatol":1.0, "fatol":1e-7, "maxiter":2000})
caf_fit, car_fit = float(res.x[0]), float(res.x[1])
pegged = (caf_fit >= 9.9e5) or (car_fit >= 9.9e5)
print(f"V3 better-fit: C_alpha_f={caf_fit:.0f}  C_alpha_r={car_fit:.0f}  pegged={pegged}  rmse={res.fun:.5f}")
st_pred_fit = T.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, caf_fit, car_fit)
v3_resid = st_pred_fit - meas
bias_corr3 = np.zeros_like(v3_resid)
for seg, sub in df.groupby("__source__"):
    idx = sub.index.to_numpy()
    d_sub = delta[idx]
    mask = np.abs(d_sub) < 0.01
    if mask.sum() > 5:
        b = np.nanmean(v3_resid[idx][mask])
    else:
        b = 0.0
    bias_corr3[idx] = b
v3_resid_corr = v3_resid - bias_corr3

# ----- V4: residual learner (LOO Ridge) trained on V3 residuals
df_v3 = df.copy()
df_v3["yaw_rate_resid_rads"] = v3_resid_corr
oof, info = T.residual_learner_loo(df_v3, residual_col="yaw_rate_resid_rads")
v4_resid = v3_resid_corr - oof

# -- summarise per-regime RMSE
def summary(resid):
    tmp = df.copy()
    tmp["r"] = resid
    return T.per_regime_rmse(tmp, "r")

rows = []
for name, r in [("V0_baseline", v0_resid),
                ("V1_KS_recal", v1_resid_corr),
                ("V2_ST_prior", v2_resid_corr),
                ("V3_ST_fit",   v3_resid_corr),
                ("V4_ridge",    v4_resid)]:
    s = summary(r)
    rows.append({"variant": name, **{k: round(v,5) for k,v in s.items()}})

rep = pd.DataFrame(rows)
print(rep.to_string(index=False))

# attribution column: drop in overall RMSE vs previous variant
overall = rep["overall"].tolist()
attrib = [None]
for i in range(1, len(overall)):
    attrib.append(round(overall[i-1] - overall[i], 5))
rep["attribution_drop_vs_prev"] = attrib
rep.to_csv(HERE / "ladder_results.csv", index=False)

# also save fit params + meta
meta = {
    "platform": PLATFORM,
    "n_segments": len(csv_paths),
    "n_rows": int(len(df)),
    "L": L, "l_f": l_f, "l_r": l_r, "m": m, "I_z": I_z,
    "C_alpha_f_prior": CAF0, "C_alpha_r_prior": CAR0,
    "C_alpha_f_fit": caf_fit, "C_alpha_r_fit": car_fit, "pegged": pegged,
    "v3_resid_learner_oof_rmse": info["oof_rmse"],
}
(HERE / "meta.json").write_text(json.dumps(meta, indent=2))
print("wrote", HERE / "ladder_results.csv")
print("wrote", HERE / "meta.json")
