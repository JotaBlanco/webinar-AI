"""Variant ladder for lateral fidelity on FORD_MUSTANG_MACH_E_MK1.

Residual sign convention: pred - meas.
ISO 8855: left positive.
Speed v and steering delta are clamped (rule 5) — speed-state agreement is by construction.
Platform scored: FORD_MUSTANG_MACH_E_MK1 (Ford — yaw_rate_meas_rads is *measured truth*).
"""
import glob
import os
import numpy as np
import pandas as pd

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIM_DIR = os.path.join(BASE, "data", "sim", "segments", PLATFORM)

csvs = sorted(glob.glob(os.path.join(SIM_DIR, "*", "*", "*", "sim.csv")))
print(f"Found {len(csvs)} segments for {PLATFORM}")

# Load all segments, tagging by segment id.
dfs = []
for p in csvs:
    seg_id = "/".join(p.split("/")[-4:-1])  # device/route/idx
    try:
        d = pd.read_csv(p)
    except Exception as e:
        continue
    if "yaw_rate_meas_rads" not in d.columns or "yaw_rate_pred_rads" not in d.columns:
        continue
    if len(d) < 50:
        continue
    d["seg_id"] = seg_id
    dfs.append(d)

df = pd.concat(dfs, ignore_index=True)
print(f"Total samples: {len(df)}  segments: {df.seg_id.nunique()}")

# Drop NaN truth/pred rows
df = df.dropna(subset=["yaw_rate_meas_rads", "yaw_rate_pred_rads", "v_mps", "delta_road_rad"]).reset_index(drop=True)
print(f"After NaN drop: {len(df)}")

# Sanity check: corr(delta_road, yaw_rate_meas) on cornering must be positive (rule 2 / ISO 8855).
corner_mask_all = df["yaw_rate_meas_rads"].abs() > 0.05
c = np.corrcoef(df.loc[corner_mask_all, "delta_road_rad"], df.loc[corner_mask_all, "yaw_rate_meas_rads"])[0, 1]
print(f"Sign-convention sanity: corr(delta_road, yaw_rate_meas | cornering) = {c:.3f}  (must be > 0)")

# ---------------- Regime masks (defined once, used for ALL variants) ----------------
yaw_meas = df["yaw_rate_meas_rads"].values
v = df["v_mps"].values

# straight: |yaw_rate_meas| < 0.02 rad/s and v > 3 m/s
straight_mask = (np.abs(yaw_meas) < 0.02) & (v > 3.0)
# transient: |d(yaw_meas)/dt| big (per-segment finite difference)
yaw_dot = np.zeros_like(yaw_meas)
for seg, idx in df.groupby("seg_id").groups.items():
    idx = np.array(sorted(idx))
    y = yaw_meas[idx]
    yaw_dot[idx[1:-1]] = (y[2:] - y[:-2]) / 0.04  # 50 Hz, central diff
transient_mask = (np.abs(yaw_meas) > 0.05) & (np.abs(yaw_dot) > 0.15)
steady_mask = (np.abs(yaw_meas) > 0.05) & ~transient_mask
# overall "in regime" mask = union of the three (this is what we score variants on, fixed across rows)
regime_mask = straight_mask | steady_mask | transient_mask
print(f"Regime counts — straight={straight_mask.sum()}  steady={steady_mask.sum()}  transient={transient_mask.sum()}  total={regime_mask.sum()}")

# ---------------- Train/test interleaved split (rule 7) ----------------
# every 5th sample → test (within the regime mask)
idx_in = np.where(regime_mask)[0]
test_mask = np.zeros_like(regime_mask)
test_mask[idx_in[::5]] = True
train_mask = regime_mask & ~test_mask

def rmse(resid, mask):
    r = resid[mask]
    if len(r) == 0:
        return float("nan")
    return float(np.sqrt(np.mean(r ** 2)))

def report_row(name, resid):
    return {
        "variant": name,
        "RMSE_all_test_rads": rmse(resid, test_mask),
        "RMSE_straight_test": rmse(resid, straight_mask & test_mask),
        "RMSE_steady_test":   rmse(resid, steady_mask & test_mask),
        "RMSE_transient_test":rmse(resid, transient_mask & test_mask),
        "n_test": int(test_mask.sum()),
    }

results = []

# -------- V0: baseline — yaw_rate_resid_rads as-is, no preprocessing (rule 10)
resid_v0 = df["yaw_rate_resid_rads"].values.copy()
# safety: recompute from pred-meas to be sure of sign
resid_v0_recomp = df["yaw_rate_pred_rads"].values - df["yaw_rate_meas_rads"].values
# they should match within float
results.append(report_row("V0 baseline (pred - meas, no preprocessing)", resid_v0_recomp))

# -------- V1: per-platform constant bias removal (median of train residual)
bias_v1 = float(np.median(resid_v0_recomp[train_mask]))
resid_v1 = resid_v0_recomp - bias_v1
results.append(report_row(f"V1 per-platform bias removal (b={bias_v1:+.5f} rad/s)", resid_v1))

# -------- V2: per-platform global gain on yaw_rate_pred (fit alpha so that alpha*pred - meas minimises RMSE on train)
# Solve alpha via least squares: minimise || alpha*pred - meas - b ||  with bias also free.
# Use train rows.
yp = df["yaw_rate_pred_rads"].values
ym = df["yaw_rate_meas_rads"].values
A = np.column_stack([yp[train_mask], np.ones(train_mask.sum())])
coef, *_ = np.linalg.lstsq(A, ym[train_mask], rcond=None)
alpha_v2, beta_v2 = float(coef[0]), float(coef[1])
pred_v2 = alpha_v2 * yp + beta_v2
resid_v2 = pred_v2 - ym
results.append(report_row(f"V2 per-platform affine gain+bias on yaw_pred (α={alpha_v2:.4f}, β={beta_v2:+.5f})", resid_v2))

# -------- V3: lag alignment — measurement lags prediction (or vice versa). Find integer-sample shift k in [-10..+10]
# that minimises train residual variance after shifting pred. Apply per-segment to avoid bleed across segments.
best_k = 0
best_rmse = np.inf
for k in range(-10, 11):
    # shift pred by k samples within each seg
    shifted = np.full_like(yp, np.nan)
    for seg, idx in df.groupby("seg_id").groups.items():
        idx = np.array(sorted(idx))
        src = yp[idx]
        if k >= 0:
            shifted[idx[k:]] = src[:len(src)-k] if k > 0 else src
        else:
            shifted[idx[:k]] = src[-k:]
    pred_k = alpha_v2 * shifted + beta_v2
    resid_k = pred_k - ym
    m = train_mask & np.isfinite(resid_k)
    r = float(np.sqrt(np.mean(resid_k[m] ** 2)))
    if r < best_rmse:
        best_rmse = r
        best_k = k

# apply best_k
shifted = np.full_like(yp, np.nan)
for seg, idx in df.groupby("seg_id").groups.items():
    idx = np.array(sorted(idx))
    src = yp[idx]
    if best_k >= 0:
        shifted[idx[best_k:]] = src[:len(src)-best_k] if best_k > 0 else src
    else:
        shifted[idx[:best_k]] = src[-best_k:]
pred_v3 = alpha_v2 * shifted + beta_v2
resid_v3 = pred_v3 - ym
# Only score where shifted is finite — keep test_mask intersection valid
valid_v3 = np.isfinite(resid_v3)
def rmse_v3(mask):
    m = mask & valid_v3
    if m.sum() == 0:
        return float("nan")
    return float(np.sqrt(np.mean(resid_v3[m] ** 2)))
row_v3 = {
    "variant": f"V3 + per-segment lag align (k={best_k} samples = {best_k*20} ms)",
    "RMSE_all_test_rads": rmse_v3(test_mask),
    "RMSE_straight_test": rmse_v3(straight_mask & test_mask),
    "RMSE_steady_test":   rmse_v3(steady_mask & test_mask),
    "RMSE_transient_test":rmse_v3(transient_mask & test_mask),
    "n_test": int(test_mask.sum()),
}
results.append(row_v3)

# -------- V4: per-segment bias removal (calibration — flagged per rule 8)
# add a per-segment median residual subtraction on top of V3
bias_by_seg = {}
for seg, idx in df.groupby("seg_id").groups.items():
    idx = np.array(sorted(idx))
    m = train_mask[idx] & valid_v3[idx]
    if m.sum() < 20:
        bias_by_seg[seg] = 0.0
    else:
        bias_by_seg[seg] = float(np.median(resid_v3[idx][m]))

per_seg_bias = df["seg_id"].map(bias_by_seg).values
resid_v4 = resid_v3 - per_seg_bias
valid_v4 = np.isfinite(resid_v4)
def rmse_v4(mask):
    m = mask & valid_v4
    if m.sum() == 0:
        return float("nan")
    return float(np.sqrt(np.mean(resid_v4[m] ** 2)))
row_v4 = {
    "variant": "V4 + per-segment bias (CALIBRATION, not model improvement — rule 8)",
    "RMSE_all_test_rads": rmse_v4(test_mask),
    "RMSE_straight_test": rmse_v4(straight_mask & test_mask),
    "RMSE_steady_test":   rmse_v4(steady_mask & test_mask),
    "RMSE_transient_test":rmse_v4(transient_mask & test_mask),
    "n_test": int(test_mask.sum()),
}
results.append(row_v4)

# Marginal contributions (strict, in V0->V_last order)
out = pd.DataFrame(results)
print()
print(out.to_string(index=False))

# Marginal deltas on all-test RMSE
prev = None
print("\nStrict marginal contribution (V0 -> ... -> V_last) on RMSE_all_test_rads (deg/s for readability):")
for _, row in out.iterrows():
    rms_deg = row["RMSE_all_test_rads"] * 180.0 / np.pi
    if prev is None:
        print(f"  {row['variant']:60s}  {rms_deg:.4f} deg/s   (baseline)")
    else:
        delta = (prev - row["RMSE_all_test_rads"]) * 180.0 / np.pi
        pct = 100.0 * (prev - row["RMSE_all_test_rads"]) / prev
        sign = "↓" if delta > 0 else "↑"
        print(f"  {row['variant']:60s}  {rms_deg:.4f} deg/s   {sign} {abs(delta):.4f} ({pct:+.1f}%)")
    prev = row["RMSE_all_test_rads"]

# Save numerical csv for the report
out_csv = os.path.join(BASE, "out", "variant_ladder.csv")
os.makedirs(os.path.dirname(out_csv), exist_ok=True)
out_to_save = out.copy()
for c2 in ["RMSE_all_test_rads", "RMSE_straight_test", "RMSE_steady_test", "RMSE_transient_test"]:
    out_to_save[c2.replace("_rads","_degps").replace("_test","_test_degps")] = out_to_save[c2] * 180.0/np.pi
out_to_save.to_csv(out_csv, index=False)
print(f"\nSaved: {out_csv}")
print(f"\nfit: alpha={alpha_v2:.4f}  beta={beta_v2:+.5f} rad/s  best_lag_k={best_k} samples ({best_k*20} ms)")
print(f"V1 platform bias: {bias_v1:+.5f} rad/s ({bias_v1*180/np.pi:+.3f} deg/s)")
