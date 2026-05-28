"""Variant ladder runner — lateral fidelity on Ford Mach-E.

Reads all Mach-E sim.csv files, computes yaw-rate-residual RMSE for:
  V0 baseline (yaw_rate_resid as-is)
  V1 per-segment straight-line yaw-rate bias removal
  V2 linear ST with openpilot-prior C_alpha (no fit)
  V3 linear ST with fit C_alpha (LOSO)
  V4 Ridge residual learner on [v, |a_y|, |delta|, sign(ddelta/dt)] (LOSO)

All variants score on the *same* sample set and the *same* regime mask. Output:
  out/ladder.csv      — variant x regime RMSE table + marginal drops
"""

from __future__ import annotations
import glob
import os
import sys
import numpy as np
import pandas as pd

# Use Mach-E (most segments, has truth).
PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
MODULE = "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-4/agent-03"
SEG_GLOB = f"{MODULE}/data/sim/segments/{PLATFORM}/*/*/*/sim.csv"
OUT_DIR = f"{MODULE}/out"
os.makedirs(OUT_DIR, exist_ok=True)

# Mach-E params
L = 2.984
m = 2336.0
I_z = 4879.05
l_f = 1.313
l_r = 1.671
Caf_prior = 286551.0
Car_prior = 355912.0

V_MIN = 2.0
STRAIGHT_THR = 0.01           # |delta_road| < 0.01 rad
DDELTA_THR = 0.05             # rad/s

print(f"Loading Mach-E segments from {SEG_GLOB}", flush=True)
seg_paths = sorted(glob.glob(SEG_GLOB))
print(f"  found {len(seg_paths)} sim.csv files", flush=True)

# To keep the run snappy under the 15-min budget, subsample segments deterministically.
MAX_SEGS = 80
if len(seg_paths) > MAX_SEGS:
    step = len(seg_paths) // MAX_SEGS
    seg_paths = seg_paths[::step][:MAX_SEGS]
print(f"  using {len(seg_paths)} segments", flush=True)


def load_segment(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["seg"] = path
    # Derived: dt of steering angle for regime
    df["ddelta_road"] = np.gradient(df["delta_road_rad"].values, df["t_s"].values)
    return df


frames = [load_segment(p) for p in seg_paths]
data = pd.concat(frames, ignore_index=True)
print(f"  total samples: {len(data)}", flush=True)

# Drop unusable samples (low speed where KS singularity / regime undefined).
data = data[data["v_mps"] >= V_MIN].reset_index(drop=True)
print(f"  after v>={V_MIN}: {len(data)}", flush=True)

# Sign sanity on cornering subset
corner_mask = data["delta_road_rad"].abs() >= STRAIGHT_THR
sign_corr = np.corrcoef(
    data.loc[corner_mask, "delta_road_rad"],
    data.loc[corner_mask, "yaw_rate_meas_rads"],
)[0, 1]
print(f"  sign sanity corr(delta_road, yaw_rate_meas) on corners = {sign_corr:.3f}", flush=True)

# Regimes
abs_d = data["delta_road_rad"].abs()
abs_dd = data["ddelta_road"].abs()
regime = np.full(len(data), "straight", dtype=object)
regime[(abs_d >= STRAIGHT_THR) & (abs_dd < DDELTA_THR)] = "steady"
regime[(abs_d >= STRAIGHT_THR) & (abs_dd >= DDELTA_THR)] = "transient"
data["regime"] = regime
print("regime counts:", data["regime"].value_counts().to_dict(), flush=True)


def rmse(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x))))


def rmse_by_regime(resid: np.ndarray, regimes: np.ndarray) -> dict:
    out = {"overall": rmse(resid)}
    for r in ("straight", "steady", "transient"):
        sel = regimes == r
        out[r] = rmse(resid[sel]) if sel.any() else float("nan")
    return out


# -------------- V0 baseline --------------
v0 = data["yaw_rate_resid_rads"].values
res = {"V0_baseline": rmse_by_regime(v0, data["regime"].values)}

# -------------- V1 per-segment IMU-gyro bias from straight-line residual --------------
# On straight samples, KS predicts ~0 yaw rate. Any non-zero mean of resid_v0 on those
# samples is an IMU offset. Subtract that bias from resid_v0 on all samples in the seg.
bias = {}
for seg, g in data.groupby("seg"):
    s = g[g["regime"] == "straight"]
    bias[seg] = float(s["yaw_rate_resid_rads"].mean()) if len(s) > 0 else 0.0
data["bias"] = data["seg"].map(bias)
v1 = (data["yaw_rate_resid_rads"] - data["bias"]).values
res["V1_bias_per_seg"] = rmse_by_regime(v1, data["regime"].values)


# -------------- V2 linear ST with PRIOR C_alpha --------------
def st_yaw_rate_steady(v: np.ndarray, delta: np.ndarray, Caf: float, Car: float) -> np.ndarray:
    """Steady-state linear ST yaw rate gain: psi_dot = v*delta / (L*(1 + K_us*v^2))."""
    K_us = m * (l_r * Car - l_f * Caf) / (L * L * Caf * Car)
    denom = L * (1.0 + K_us * v * v)
    return v * delta / denom


v = data["v_mps"].values
delta = data["delta_road_rad"].values
meas = data["yaw_rate_meas_rads"].values
st_prior = st_yaw_rate_steady(v, delta, Caf_prior, Car_prior)
# Apply v1's bias too (cumulative ladder); ST replaces the KS prediction.
v2 = (st_prior - meas) - data["bias"].values
res["V2_ST_prior_Calpha"] = rmse_by_regime(v2, data["regime"].values)


# -------------- V3 linear ST with FIT C_alpha (LOSO) --------------
# Fit two parameters (Caf, Car) by least squares against meas - bias, leave one
# segment out at a time. Bounded: physical range ~50k..500k N/rad.
from scipy.optimize import minimize

segs = data["seg"].unique().tolist()
seg_idx = {s: i for i, s in enumerate(segs)}
data["seg_id"] = data["seg"].map(seg_idx)
# Fit ST so that st_pred(v, delta) ≈ meas + bias_seg (since bias_seg is subtracted from final residual)
target = meas + data["bias"].values

bounds = [(5e4, 5e5), (5e4, 5e5)]


def loss_factory(vv, dd, tt):
    def loss(theta):
        Caf, Car = theta
        pred = st_yaw_rate_steady(vv, dd, Caf, Car)
        return float(np.mean((pred - tt) ** 2))
    return loss


loso_preds = np.zeros(len(data))
fit_Caf = np.zeros(len(segs))
fit_Car = np.zeros(len(segs))
for i, s in enumerate(segs):
    mask_train = data["seg"].values != s
    mask_test = ~mask_train
    # Restrict fit to cornering samples where the ST gain matters; rescale for the optimiser.
    cmask = np.abs(delta[mask_train]) >= STRAIGHT_THR
    vv = v[mask_train][cmask]; dd = delta[mask_train][cmask]; tt = target[mask_train][cmask]
    def loss(theta):
        Caf, Car = theta[0] * 1e5, theta[1] * 1e5
        return float(np.mean((st_yaw_rate_steady(vv, dd, Caf, Car) - tt) ** 2))
    res_opt = minimize(
        loss,
        x0=np.array([Caf_prior / 1e5, Car_prior / 1e5]),
        bounds=[(0.5, 5.0), (0.5, 5.0)],
        method="L-BFGS-B",
    )
    Caf_hat, Car_hat = res_opt.x[0] * 1e5, res_opt.x[1] * 1e5
    fit_Caf[i] = Caf_hat
    fit_Car[i] = Car_hat
    loso_preds[mask_test] = st_yaw_rate_steady(v[mask_test], delta[mask_test], Caf_hat, Car_hat)

print(f"  V3 fit Caf median = {np.median(fit_Caf):.0f}, Car median = {np.median(fit_Car):.0f}", flush=True)
print(f"  V3 fit Caf min/max = {fit_Caf.min():.0f}/{fit_Caf.max():.0f}", flush=True)
v3 = (loso_preds - meas) - data["bias"].values
res["V3_ST_fit_Calpha_LOSO"] = rmse_by_regime(v3, data["regime"].values)


# -------------- V4 Ridge residual learner (LOSO) --------------
from sklearn.linear_model import Ridge

# Features: v, |a_y_pred|, |delta_road|, sign(ddelta/dt)
ay_pred = data["a_y_pred_mps2"].values
sgn = np.sign(data["ddelta_road"].values)
features = np.column_stack([v, np.abs(ay_pred), np.abs(delta), sgn])
# Target: V3 residual we want to launder
y = v3.copy()  # = (loso_st - bias) - meas
pred_resid = np.zeros_like(y)
for s in segs:
    train = data["seg"].values != s
    test = ~train
    clf = Ridge(alpha=1.0).fit(features[train], y[train])
    pred_resid[test] = clf.predict(features[test])
v4 = y - pred_resid
res["V4_Ridge_residual_LOSO"] = rmse_by_regime(v4, data["regime"].values)


# --------- Assemble table ----------
rows = []
prev_overall = None
order = ["V0_baseline", "V1_bias_per_seg", "V2_ST_prior_Calpha", "V3_ST_fit_Calpha_LOSO", "V4_Ridge_residual_LOSO"]
for name in order:
    r = res[name]
    drop = float("nan") if prev_overall is None else prev_overall - r["overall"]
    rows.append({
        "variant": name,
        "overall_rmse": r["overall"],
        "straight": r["straight"],
        "steady": r["steady"],
        "transient": r["transient"],
        "marginal_drop_from_prev": drop,
    })
    prev_overall = r["overall"]

ladder = pd.DataFrame(rows)
total_drop = rows[0]["overall_rmse"] - rows[-1]["overall_rmse"]
sum_marg = sum(r["marginal_drop_from_prev"] for r in rows if not np.isnan(r["marginal_drop_from_prev"]))
print(ladder.to_string(index=False))
print(f"Total V0->V_last drop: {total_drop:.5f}")
print(f"Sum of marginals     : {sum_marg:.5f}")
print(f"Drift                 : {abs(sum_marg - total_drop):.5f} ({100*abs(sum_marg-total_drop)/total_drop:.1f}% of total)")
ladder.to_csv(f"{OUT_DIR}/ladder.csv", index=False)
print(f"wrote {OUT_DIR}/ladder.csv")
