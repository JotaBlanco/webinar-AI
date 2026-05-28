"""Lateral fidelity ladder: compute V0..V3 RMSE on yaw_rate, with marginal attribution.

Platform: FORD_MUSTANG_MACH_E_MK1 (truth available, larger segment count)
Truth channel: yaw_rate_meas_rads (decoded from Ford CAN IMU, MEASURED, not self-consistency).
Contract: v and delta clamped to measured; only lateral states (psi_dot, a_y) are predicted.

Variants:
  V0 baseline                : pred as-is
  V1 + per-segment bias removal  : subtract per-segment mean(residual) from pred
  V2 + global understeer gain    : scale (pred - bias) by best constant gain K* (closes linear
                                   understeer leakage that KS ignores by assumption)
  V3 + speed-dependent understeer: pred *= 1/(1 + Kus * v^2), Kus fit globally
       (recovers the ST steady-state yaw-rate gain shape from KS)

Marginal attribution: each row's drop = RMSE(prev) - RMSE(this).  Sum should match V0 - V3.
"""
import glob, os, json
import numpy as np
import pandas as pd

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
SIM_GLOB = f"/Users/javiquix/Desktop/quixdev/webinar-AI/data/sim/segments/{PLATFORM}/*/*/*/sim.csv"

files = sorted(glob.glob(SIM_GLOB))
print(f"segments: {len(files)}")

# ---- Load all segments, tag with seg id, build a single long frame
frames = []
for f in files:
    df = pd.read_csv(f)
    # seg id = device/route/idx
    parts = f.split("/")
    seg_id = "/".join(parts[-4:-1])
    df["seg_id"] = seg_id
    frames.append(df)
big = pd.concat(frames, ignore_index=True)
print("rows:", len(big))

# Drop rows with NaN in the channels we need
need = ["yaw_rate_pred_rads", "yaw_rate_meas_rads", "v_mps", "delta_road_rad"]
big = big.dropna(subset=need).reset_index(drop=True)
print("rows after dropna:", len(big))

# ---- Regime mask (consistent across all variants)
# Use steering rate + |yaw_rate_meas| to classify
v = big["v_mps"].values
delta = big["delta_road_rad"].values
psi_dot_meas = big["yaw_rate_meas_rads"].values

# steering rate (rad/s) per segment using simple diff
big["delta_dot"] = big.groupby("seg_id")["delta_road_rad"].diff() / 0.02
big["delta_dot"] = big["delta_dot"].fillna(0.0)

abs_yr = np.abs(psi_dot_meas)
abs_dd = np.abs(big["delta_dot"].values)

STRAIGHT = abs_yr < 0.05         # rad/s
STEADY   = (abs_yr >= 0.05) & (abs_dd < 0.05)
TRANSIENT = (abs_yr >= 0.05) & (abs_dd >= 0.05)
# (regimes are exhaustive and disjoint)

big["regime"] = np.select(
    [STRAIGHT, STEADY, TRANSIENT],
    ["straight", "steady", "transient"],
    default="other",
)
print(big["regime"].value_counts().to_dict())

# ---- Helper: RMSE by regime
def rmse_by_regime(resid, regimes):
    out = {}
    out["all"] = float(np.sqrt(np.mean(resid**2)))
    for r in ["straight", "steady", "transient"]:
        m = regimes == r
        if m.any():
            out[r] = float(np.sqrt(np.mean(resid[m]**2)))
        else:
            out[r] = float("nan")
    return out

pred0 = big["yaw_rate_pred_rads"].values.copy()
meas  = big["yaw_rate_meas_rads"].values
regs  = big["regime"].values

# ---- V0: baseline (use the precomputed residual to verify)
resid0 = pred0 - meas
v0 = rmse_by_regime(resid0, regs)
print("V0:", v0)

# ---- V1: per-segment bias removal
# Compute per-segment mean residual on STRAIGHT samples (most honest bias estimate) and
# subtract from pred for the whole segment.
big["resid0"] = resid0
seg_bias = (
    big[big["regime"] == "straight"]
    .groupby("seg_id")["resid0"].mean()
    .rename("bias")
)
big = big.merge(seg_bias, on="seg_id", how="left")
big["bias"] = big["bias"].fillna(big["resid0"].mean())  # fallback global
pred1 = pred0 - big["bias"].values
resid1 = pred1 - meas
v1 = rmse_by_regime(resid1, regs)
print("V1:", v1)

# ---- V2: global understeer gain K*  (linear scaling of pred)
# Find K minimizing RMSE of (K*pred1 - meas) on cornering rows where it matters.
mask_c = regs != "straight"
A = pred1[mask_c]
b = meas[mask_c]
K_star = float(np.dot(A, b) / np.dot(A, A))
print(f"K* = {K_star:.4f}")
pred2 = K_star * pred1
resid2 = pred2 - meas
v2 = rmse_by_regime(resid2, regs)
print("V2:", v2)

# ---- V3: speed-dependent understeer  pred *= 1 / (1 + Kus * v^2)
# Fit Kus globally on cornering rows: minimise RMSE of  pred1 / (1+Kus v^2) - meas
from scipy.optimize import minimize_scalar
v_c = v[mask_c]
p_c = pred1[mask_c]
m_c = meas[mask_c]
def obj(Kus):
    pred = p_c / (1.0 + Kus * v_c**2)
    return np.mean((pred - m_c) ** 2)
res = minimize_scalar(obj, bounds=(-0.01, 0.02), method="bounded")
Kus = float(res.x)
print(f"Kus = {Kus:.6f}  (units 1/(m/s)^2 -> understeer coefficient)")
pred3 = pred1 / (1.0 + Kus * v**2)
resid3 = pred3 - meas
v3 = rmse_by_regime(resid3, regs)
print("V3:", v3)

# ---- Marginal attribution
def drop(prev, cur):
    return {k: prev[k] - cur[k] for k in prev}

m1 = drop(v0, v1)
m2 = drop(v1, v2)
m3 = drop(v2, v3)
total = drop(v0, v3)
print("marginal V1:", m1)
print("marginal V2:", m2)
print("marginal V3:", m3)
print("total V0->V3:", total)
print("sum_marginals:", {k: m1[k] + m2[k] + m3[k] for k in m1})

# ---- Save artifact
summary = {
    "platform": PLATFORM,
    "n_segments": len(files),
    "n_rows": int(len(big)),
    "regime_counts": big["regime"].value_counts().to_dict(),
    "K_star": K_star,
    "Kus": Kus,
    "V0": v0, "V1": v1, "V2": v2, "V3": v3,
    "marginal": {"V1": m1, "V2": m2, "V3": m3},
    "total_drop": total,
    "sum_marginals": {k: m1[k] + m2[k] + m3[k] for k in m1},
}
out = "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-2/agent-04/out/summary.json"
with open(out, "w") as f:
    json.dump(summary, f, indent=2)
print("wrote", out)
