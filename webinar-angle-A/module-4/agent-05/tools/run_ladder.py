"""Variant ladder analysis — lateral fidelity on Ford Mach-E."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
MODULE = HERE.parent
sys.path.insert(0, str(MODULE / "skills" / "lateral-fidelity-triage"))
sys.path.insert(0, str(MODULE / "code"))

import triage  # noqa: E402
from parameters import PARAM_BY_PLATFORM  # noqa: E402


PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
SEG_ROOT = MODULE / "data" / "sim" / "segments" / PLATFORM
OUT = MODULE / "out"
OUT.mkdir(exist_ok=True)

# Take a deterministic sample of segments — 40 segs is enough for stable RMSE
all_segs = sorted(SEG_ROOT.rglob("sim.csv"))
print(f"Found {len(all_segs)} {PLATFORM} segments")
rng = np.random.default_rng(42)
idx = rng.choice(len(all_segs), size=min(40, len(all_segs)), replace=False)
seg_paths = [all_segs[i] for i in sorted(idx)]
print(f"Using {len(seg_paths)} segments")

df = triage.load_many(seg_paths)
print(f"Total rows: {len(df)}")

p = PARAM_BY_PLATFORM[PLATFORM]
L, l_f, l_r, m, I_z = p.L, p.l_f, p.l_r, p.m, p.I_z
Caf_prior, Car_prior = p.C_alpha_f, p.C_alpha_r

# ----- Build per-variant residual columns -----
v = df["v_mps"].to_numpy()
delta = df["delta_road_rad"].to_numpy()
meas = df["yaw_rate_meas_rads"].to_numpy()

# V0: residual already in CSV (pred − meas, KS as shipped)
df["resid_V0"] = df["yaw_rate_resid_rads"]

# V1: KS recalibrated — recompute with canonical L, subtract per-segment straight bias
ks_pred = triage.ks_yaw_rate(v, delta, L)
df["pred_V1_raw"] = ks_pred
df["resid_V1_pre"] = ks_pred - meas

# per-segment bias on straight samples
biases = {}
for src, sub in df.groupby("__source__"):
    straight = np.abs(sub["delta_road_rad"].to_numpy()) < 0.01
    if straight.sum() > 5:
        biases[src] = float(np.nanmean(sub.loc[straight, "resid_V1_pre"]))
    else:
        biases[src] = 0.0
bias_arr = df["__source__"].map(biases).to_numpy()
df["resid_V1"] = df["resid_V1_pre"] - bias_arr

# V2: linear ST with prior C_alpha
st_pred_prior = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, Caf_prior, Car_prior)
# Apply same per-segment bias subtraction (now on V2 residual) — keep consistent
df["resid_V2_pre"] = st_pred_prior - meas
biases_v2 = {}
for src, sub in df.groupby("__source__"):
    straight = np.abs(sub["delta_road_rad"].to_numpy()) < 0.01
    if straight.sum() > 5:
        biases_v2[src] = float(np.nanmean(sub.loc[straight, "resid_V2_pre"]))
    else:
        biases_v2[src] = 0.0
bias_arr_v2 = df["__source__"].map(biases_v2).to_numpy()
df["resid_V2"] = df["resid_V2_pre"] - bias_arr_v2

# V3: linear ST with fit C_alpha (fit on bias-corrected data)
# We minimise RMSE of (st_pred(cf,cr) - bias) - meas
from scipy.optimize import minimize


def loss_v3(params):
    cf, cr = params
    pred = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, cf, cr)
    # apply per-segment straight bias derived from this prediction
    err = pred - meas
    # subtract per-segment straight-mean bias
    src_arr = df["__source__"].to_numpy()
    err_corr = err.copy()
    for src in np.unique(src_arr):
        mask_seg = src_arr == src
        straight_seg = mask_seg & (np.abs(delta) < 0.01)
        if straight_seg.sum() > 5:
            b = float(np.nanmean(err[straight_seg]))
            err_corr[mask_seg] = err[mask_seg] - b
    e = err_corr[np.isfinite(err_corr)]
    return float(np.sqrt(np.mean(e ** 2)))


# Coarse grid then refine — local gradient is too flat for L-BFGS-B from a single x0
grid = np.linspace(5e4, 5e5, 12)
best_loss = float("inf")
best_cf, best_cr = Caf_prior, Car_prior
for cf_try in grid:
    for cr_try in grid:
        ll = loss_v3([cf_try, cr_try])
        if ll < best_loss:
            best_loss = ll
            best_cf, best_cr = cf_try, cr_try
res = minimize(
    loss_v3,
    x0=[best_cf, best_cr],
    method="L-BFGS-B",
    bounds=[(5e4, 5e5), (5e4, 5e5)],
)
cf_fit, cr_fit = float(res.x[0]), float(res.x[1])
pegged = (abs(cf_fit - 5e5) < 1.0) or (abs(cr_fit - 5e5) < 1.0)
print(f"V3 fit (grid+refine): C_af={cf_fit:.0f}  C_ar={cr_fit:.0f}  pegged={pegged}  loss={res.fun:.6f}")

st_pred_fit = triage.linear_st_yaw_rate(v, delta, L, l_f, l_r, m, I_z, cf_fit, cr_fit)
df["resid_V3_pre"] = st_pred_fit - meas
biases_v3 = {}
for src, sub in df.groupby("__source__"):
    straight = np.abs(sub["delta_road_rad"].to_numpy()) < 0.01
    if straight.sum() > 5:
        biases_v3[src] = float(np.nanmean(sub.loc[straight, "resid_V3_pre"]))
    else:
        biases_v3[src] = 0.0
bias_arr_v3 = df["__source__"].map(biases_v3).to_numpy()
df["resid_V3"] = df["resid_V3_pre"] - bias_arr_v3

# V4: residual learner LOO on V3 residuals
from sklearn.linear_model import Ridge

t = df["t_s"].to_numpy()
dt = np.diff(t, prepend=t[0])
dt = np.where(dt > 0, dt, 0.02)
ddelta = np.gradient(delta) / dt
a_y_p = df["a_y_pred_mps2"].to_numpy() if "a_y_pred_mps2" in df.columns else np.zeros(len(df))
X = np.column_stack([v, np.abs(a_y_p), np.abs(delta), np.sign(ddelta)])
y_v3 = df["resid_V3"].to_numpy()
src_arr = df["__source__"].to_numpy()
oof = np.full(len(df), np.nan)
for seg in np.unique(src_arr):
    train = src_arr != seg
    test = ~train
    finite = np.isfinite(y_v3[train])
    model = Ridge(alpha=1.0).fit(X[train][finite], y_v3[train][finite])
    oof[test] = model.predict(X[test])
df["resid_V4"] = y_v3 - oof

# ----- Regimes -----
df["regime"] = triage.regime_mask(df)

variants = ["V0", "V1", "V2", "V3", "V4"]
labels = {
    "V0": "KS (as shipped)",
    "V1": "KS recalibrated + per-seg bias",
    "V2": "Linear ST, prior C_alpha + bias",
    "V3": "Linear ST, fit C_alpha + bias",
    "V4": "V3 + Ridge residual learner (LOO)",
}

rows = []
for vname in variants:
    col = f"resid_{vname}"
    overall = triage.rmse(df[col])
    per = {}
    for r in ("straight", "steady", "transient"):
        sub = df.loc[df["regime"] == r, col]
        per[r] = triage.rmse(sub)
    rows.append({
        "variant": vname,
        "label": labels[vname],
        "overall": overall,
        **per,
    })

ladder = pd.DataFrame(rows)

# marginal drops on overall (V_{i-1} − V_i, positive = improvement)
ladder["marginal_drop"] = [np.nan] + [
    ladder["overall"].iloc[i - 1] - ladder["overall"].iloc[i]
    for i in range(1, len(ladder))
]

ladder.to_csv(OUT / "variant_ladder.csv", index=False)

print("\nVariant ladder:")
print(ladder.to_string(index=False))

total_drop = ladder["overall"].iloc[0] - ladder["overall"].iloc[-1]
sum_marg = ladder["marginal_drop"].dropna().sum()
print(f"\nTotal V0→V_last drop: {total_drop:.5f}")
print(f"Sum of marginals    : {sum_marg:.5f}")
print(f"Attribution error   : {abs(sum_marg - total_drop) / abs(total_drop):.4f}")

print(f"\nFit Cα results: C_af={cf_fit:.0f} N/rad, C_ar={cr_fit:.0f} N/rad  pegged={pegged}")
print(f"Number of segments used: {df['__source__'].nunique()}")
print(f"Total samples: {len(df)}")
regime_counts = df["regime"].value_counts().to_dict()
print(f"Regime counts: {regime_counts}")

# Save summary metadata
with open(OUT / "summary.txt", "w") as fh:
    fh.write(f"platform={PLATFORM}\n")
    fh.write(f"n_segments={df['__source__'].nunique()}\n")
    fh.write(f"n_samples={len(df)}\n")
    fh.write(f"regimes={regime_counts}\n")
    fh.write(f"cf_prior={Caf_prior}\ncr_prior={Car_prior}\n")
    fh.write(f"cf_fit={cf_fit:.1f}\ncr_fit={cr_fit:.1f}\npegged={pegged}\n")
    fh.write(f"total_drop={total_drop:.6f}\n")
    fh.write(f"sum_marginal={sum_marg:.6f}\n")
    fh.write(f"attribution_err={abs(sum_marg - total_drop) / abs(total_drop):.4f}\n")
