"""Lateral-fidelity variant ladder for FORD_MUSTANG_MACH_E_MK1.

Speed-known framing (clamped v, delta). Truth = yaw_rate_meas_rads.

V0  : KS as-is (residual from sim.csv).
V1  : KS + per-segment yaw-rate bias (straight-line offset cancellation).
V2  : Linear ST (steady-state), prior C_alpha from PARAM_BY_PLATFORM.
V3  : Linear ST with fit C_alpha (single global fit, bounded 50-500 kN/rad)
      + per-segment bias.

Marginal accounting scheme: cumulative RMSE drop per rung, with marginal column
= prev_rmse - this_rmse.
"""
from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "code"))
from parameters import PARAM_BY_PLATFORM  # noqa: E402

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
P = PARAM_BY_PLATFORM[PLATFORM]

SIM_ROOT = ROOT / "data" / "sim" / "segments" / PLATFORM

# ----- load segments --------------------------------------------------------

paths = sorted(SIM_ROOT.glob("*/*/*/sim.csv"))
print(f"# segments: {len(paths)}")

# subsample to keep runtime small but representative
RNG = np.random.default_rng(0)
if len(paths) > 120:
    idx = RNG.choice(len(paths), 120, replace=False)
    paths = [paths[i] for i in sorted(idx)]
print(f"# using segments: {len(paths)}")

rows = []
for sid, p in enumerate(paths):
    try:
        df = pd.read_csv(p)
    except Exception:
        continue
    if len(df) < 50:
        continue
    df = df.copy()
    df["seg_id"] = sid
    rows.append(df)
all_df = pd.concat(rows, ignore_index=True)
print(f"# total samples: {len(all_df)}")

# ----- regime mask ----------------------------------------------------------

dt = 0.02
# dδ/dt per segment (numerical), then back to flat df
ddelta = np.zeros(len(all_df))
for sid, g in all_df.groupby("seg_id", sort=False):
    delta = g["delta_road_rad"].values
    dd = np.gradient(delta, dt)
    ddelta[g.index] = dd
all_df["ddelta_dt"] = ddelta

# moving regime
straight = np.abs(all_df["delta_road_rad"]) < 0.01
steady = (~straight) & (np.abs(all_df["ddelta_dt"]) < 0.05)
transient = (~straight) & (np.abs(all_df["ddelta_dt"]) >= 0.05)

# require valid measured + finite predicted, plus v > 2 m/s for ST stability
valid = (
    np.isfinite(all_df["yaw_rate_meas_rads"]).values
    & np.isfinite(all_df["yaw_rate_pred_rads"]).values
    & (all_df["v_mps"].values > 2.0)
)
mask_all = valid

# sign sanity
corner_mask = (np.abs(all_df["delta_road_rad"]) > 0.02).values & valid
r = np.corrcoef(
    all_df["delta_road_rad"].values[corner_mask],
    all_df["yaw_rate_meas_rads"].values[corner_mask],
)[0, 1]
print(f"sign-sanity corr(delta_road, yaw_rate_meas) on |delta|>0.02 = {r:+.3f}")


def rmse(a):
    a = np.asarray(a)
    return float(np.sqrt(np.mean(a ** 2)))


def regime_breakdown(resid, mask):
    out = {}
    for name, rmask in [("all", np.ones_like(mask, dtype=bool)),
                        ("straight", straight.values),
                        ("steady", steady.values),
                        ("transient", transient.values)]:
        m = mask & rmask
        if m.sum() == 0:
            out[name] = (float("nan"), 0)
        else:
            out[name] = (rmse(resid[m]), int(m.sum()))
    return out


# ----- V0 : KS as-is --------------------------------------------------------
yaw_meas = all_df["yaw_rate_meas_rads"].values
v = all_df["v_mps"].values
delta = all_df["delta_road_rad"].values
seg_ids = all_df["seg_id"].values

yaw_v0 = all_df["yaw_rate_pred_rads"].values
res_v0 = yaw_v0 - yaw_meas

# ----- V1 : KS + per-segment bias from straight-line samples ----------------
yaw_v1 = yaw_v0.copy()
biases = {}
for sid in np.unique(seg_ids):
    m = (seg_ids == sid) & straight.values & valid
    if m.sum() < 50:
        biases[sid] = 0.0
    else:
        biases[sid] = float(np.mean(yaw_v0[m] - yaw_meas[m]))
for sid, b in biases.items():
    yaw_v1[seg_ids == sid] -= b
res_v1 = yaw_v1 - yaw_meas

# ----- V2 : Linear ST steady-state, prior C_alpha --------------------------
def st_yaw_rate(v, delta, m, L, l_f, l_r, Caf, Car):
    K_us = m * (l_r * Car - l_f * Caf) / (L ** 2 * Caf * Car)
    # numerical guard: K_us*v^2 should be small; for understeer K_us > 0
    return v * delta / (L * (1.0 + K_us * v * v))

yaw_v2 = st_yaw_rate(v, delta, P.m, P.L, P.l_f, P.l_r, P.C_alpha_f, P.C_alpha_r)
# Below 2 m/s fall back to KS; we already exclude via valid mask
res_v2 = yaw_v2 - yaw_meas

# ----- V3 : ST with fit C_alpha (assume Caf=Car=C, single param) + bias ----
# Closed form not trivial because K_us depends on Caf, Car separately.
# Practical fit: search a scalar multiplier alpha on (Caf_prior, Car_prior),
# minimising RMSE on cornering samples (|delta|>=0.01).
from scipy.optimize import minimize_scalar

corner_fit = (np.abs(delta) >= 0.01) & valid


def st_rmse(alpha):
    Caf = P.C_alpha_f * alpha
    Car = P.C_alpha_r * alpha
    yp = st_yaw_rate(v, delta, P.m, P.L, P.l_f, P.l_r, Caf, Car)
    return rmse((yp - yaw_meas)[corner_fit])


# Bound alpha so per-axle C_alpha stays in 50-500 kN/rad as per skill.
bound_lo, bound_hi = 50_000, 500_000
alpha_lo = max(bound_lo / P.C_alpha_f, bound_lo / P.C_alpha_r)
alpha_hi = min(bound_hi / P.C_alpha_f, bound_hi / P.C_alpha_r)
res_opt = minimize_scalar(st_rmse, bounds=(alpha_lo, alpha_hi), method="bounded",
                          options={"xatol": 1e-3})
alpha_fit = float(res_opt.x)
Caf_fit = P.C_alpha_f * alpha_fit
Car_fit = P.C_alpha_r * alpha_fit
print(f"fit alpha={alpha_fit:.3f}  C_af={Caf_fit:,.0f}  C_ar={Car_fit:,.0f}")
pegged = (Caf_fit <= bound_lo * 1.01) or (Caf_fit >= bound_hi * 0.99) or \
         (Car_fit <= bound_lo * 1.01) or (Car_fit >= bound_hi * 0.99)

yaw_v3 = st_yaw_rate(v, delta, P.m, P.L, P.l_f, P.l_r, Caf_fit, Car_fit)
# Per-segment bias from straight-line residuals of V3 prediction
biases3 = {}
for sid in np.unique(seg_ids):
    m = (seg_ids == sid) & straight.values & valid
    if m.sum() < 50:
        biases3[sid] = 0.0
    else:
        biases3[sid] = float(np.mean(yaw_v3[m] - yaw_meas[m]))
for sid, b in biases3.items():
    yaw_v3[seg_ids == sid] -= b
res_v3 = yaw_v3 - yaw_meas

# ----- report --------------------------------------------------------------
results = []
for name, resid in [("V0_KS", res_v0),
                    ("V1_KS_bias", res_v1),
                    ("V2_ST_prior", res_v2),
                    ("V3_STfit_bias", res_v3)]:
    rb = regime_breakdown(resid, mask_all)
    results.append((name, rb))

prev = None
print()
print(f"{'variant':<18} {'all':>10} {'straight':>10} {'steady':>10} {'transient':>10} {'marginal':>10}")
for name, rb in results:
    cur = rb["all"][0]
    marg = (prev - cur) if prev is not None else 0.0
    print(f"{name:<18} {rb['all'][0]:>10.5f} {rb['straight'][0]:>10.5f} {rb['steady'][0]:>10.5f} {rb['transient'][0]:>10.5f} {marg:>+10.5f}")
    prev = cur

total = results[0][1]["all"][0] - results[-1][1]["all"][0]
sum_marg = sum(
    (results[i - 1][1]["all"][0] - results[i][1]["all"][0])
    for i in range(1, len(results))
)
print(f"\nV0->V_last drop: {total:+.5f}  sum-of-marginals: {sum_marg:+.5f}")
print(f"sample counts (all/straight/steady/transient): "
      f"{results[0][1]['all'][1]}/"
      f"{results[0][1]['straight'][1]}/"
      f"{results[0][1]['steady'][1]}/"
      f"{results[0][1]['transient'][1]}")
print(f"C_alpha pegged at bound? {pegged}")

# Cornering-only score (steady+transient) for sanity
print()
print(f"{'variant':<18} {'cornering':>10}")
for name, rb in results:
    n_st = rb['steady'][1]
    n_tr = rb['transient'][1]
    # combine RMSE
    rb_st = rb['steady'][0]
    rb_tr = rb['transient'][0]
    if (n_st + n_tr) > 0:
        c_rmse = np.sqrt((n_st * rb_st**2 + n_tr * rb_tr**2) / (n_st + n_tr))
    else:
        c_rmse = float('nan')
    print(f"{name:<18} {c_rmse:>10.5f}")

