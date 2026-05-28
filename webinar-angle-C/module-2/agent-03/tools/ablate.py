"""Lateral fidelity ablation on FORD_MUSTANG_MACH_E_MK1.

Variants (strict marginal, applied cumulatively V0->V3):

  V0  baseline                  yaw_rate_resid_rads as-is
  V1  +per-platform bias        subtract median(pred-meas) on train half
  V2  +lag alignment            integer-sample shift of pred to maximise xcorr (per-segment)
  V3  +per-platform steer gain  k * delta_road -> rescale pred contribution

Metrics: RMSE in deg/s, per regime:
  straight:    |delta_road| < 0.005 rad
  steady:      |delta_road| >= 0.005 and |ddelta_road/dt| < 0.02 rad/s
  transient:   |ddelta_road/dt| >= 0.02 rad/s
"""
from __future__ import annotations
import glob, os, sys, math
import numpy as np
import pandas as pd

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-2/agent-03"
PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
SIM_DIR = f"{ROOT}/data/sim/segments/{PLATFORM}"
OUT_DIR = f"{ROOT}/out"
os.makedirs(OUT_DIR, exist_ok=True)

R2D = 180.0 / math.pi

# ---------- load ----------
csvs = sorted(glob.glob(f"{SIM_DIR}/**/sim.csv", recursive=True))
print(f"loaded {len(csvs)} segments from {PLATFORM}", file=sys.stderr)

segs = []
for p in csvs:
    try:
        df = pd.read_csv(p)
    except Exception as e:
        continue
    need = {"t_s","delta_road_rad","yaw_rate_meas_rads","yaw_rate_pred_rads","v_mps"}
    if not need.issubset(df.columns):
        continue
    if len(df) < 50:
        continue
    df = df.reset_index(drop=True)
    df["seg"] = p
    segs.append(df)

assert segs, "no segments"
all_df = pd.concat(segs, ignore_index=True)
print(f"total rows: {len(all_df)}", file=sys.stderr)

# ---------- positive-correlation sanity (rule 2) ----------
corner = all_df[np.abs(all_df["delta_road_rad"]) > 0.01]
corr = np.corrcoef(corner["delta_road_rad"], corner["yaw_rate_meas_rads"])[0,1]
print(f"corr(delta_road, yaw_meas) on cornering = {corr:.3f}  (must be > 0)", file=sys.stderr)
assert corr > 0, "sign convention violated"

# ---------- regime mask (computed per segment to get ddelta/dt) ----------
def regime_masks(df: pd.DataFrame):
    dr = df["delta_road_rad"].to_numpy()
    t  = df["t_s"].to_numpy()
    dt = np.gradient(t)
    ddr = np.gradient(dr) / np.where(dt==0, 1e-3, dt)
    straight  = np.abs(dr) < 0.005
    transient = np.abs(ddr) >= 0.02
    steady    = (~straight) & (~transient)
    return straight, steady, transient

# Pre-compute per-segment regime info
seg_groups = list(all_df.groupby("seg", sort=False))

# interleaved train/test (rule 7) -- every 5th sample is test
def train_test_split_idx(n):
    idx = np.arange(n)
    test = idx % 5 == 0
    train = ~test
    return train, test

# ---------- compute variants ----------
# For lag alignment (V2), we shift pred by k samples (k in -10..10) chosen per segment to maximise pearson r between pred and meas on TRAIN half.
def best_lag(pred, meas, train_mask, max_lag=10):
    best = (0, -np.inf)
    for k in range(-max_lag, max_lag+1):
        if k >= 0:
            p = np.concatenate([np.full(k, pred[0]), pred[:-k] if k>0 else pred])
        else:
            p = np.concatenate([pred[-k:], np.full(-k, pred[-1])])
        if len(p) != len(pred):
            continue
        mask = train_mask & np.isfinite(p) & np.isfinite(meas)
        if mask.sum() < 50: continue
        a = p[mask]; b = meas[mask]
        if a.std()<1e-9 or b.std()<1e-9: continue
        r = np.corrcoef(a, b)[0,1]
        if r > best[1]:
            best = (k, r)
    return best[0]

# Build a global per-platform bias (median of pred-meas on TRAIN samples, straight regime to avoid coupling with steering gain)
def compute_platform_bias(segs):
    resid_train = []
    for seg, df in segs:
        n = len(df)
        train, _ = train_test_split_idx(n)
        s, _, _ = regime_masks(df)
        m = train & s
        if m.sum() == 0: continue
        r = (df["yaw_rate_pred_rads"].to_numpy() - df["yaw_rate_meas_rads"].to_numpy())[m]
        resid_train.append(r)
    if not resid_train:
        return 0.0
    return float(np.median(np.concatenate(resid_train)))

# Per-platform steering-gain k: minimise sum (k*pred_after_bias_and_lag - meas)^2 over cornering TRAIN samples
def compute_platform_gain(segs_with_pred):
    num = 0.0; den = 0.0
    for df, p_adj in segs_with_pred:
        n = len(df)
        train, _ = train_test_split_idx(n)
        s, _, _ = regime_masks(df)
        m = train & (~s)
        m &= np.isfinite(p_adj) & np.isfinite(df["yaw_rate_meas_rads"].to_numpy())
        if m.sum() < 20: continue
        p = p_adj[m]; meas = df["yaw_rate_meas_rads"].to_numpy()[m]
        num += float(np.sum(p * meas))
        den += float(np.sum(p * p))
    return num/den if den>0 else 1.0

# ---------- variant pipeline ----------
# We build per-segment arrays of corrected pred for each variant; then evaluate on TEST samples only.

bias = compute_platform_bias(seg_groups)
print(f"V1 platform bias (pred-meas, rad/s, train-straight median) = {bias:.5f}", file=sys.stderr)

# Apply bias and compute lag per segment
segs_v2 = []
lags = []
for seg, df in seg_groups:
    pred0 = df["yaw_rate_pred_rads"].to_numpy()
    meas  = df["yaw_rate_meas_rads"].to_numpy()
    n = len(df)
    train, _ = train_test_split_idx(n)
    pred1 = pred0 - bias
    lag = best_lag(pred1, meas, train, max_lag=10)
    lags.append(lag)
    # apply lag
    if lag > 0:
        pred2 = np.concatenate([np.full(lag, pred1[0]), pred1[:-lag]])
    elif lag < 0:
        pred2 = np.concatenate([pred1[-lag:], np.full(-lag, pred1[-1])])
    else:
        pred2 = pred1.copy()
    segs_v2.append((df, pred0, pred1, pred2))
print(f"V2 per-segment lags (samples @50Hz): median={int(np.median(lags))} mean={np.mean(lags):.2f}", file=sys.stderr)

# Compute gain on bias+lag-corrected pred (cornering train)
segs_for_gain = [(df, p2) for (df, _, _, p2) in segs_v2]
k_gain = compute_platform_gain(segs_for_gain)
print(f"V3 platform gain k = {k_gain:.4f}", file=sys.stderr)

# Final per-variant arrays
def rmse(a, m):
    a = a[m]
    if len(a)==0: return float("nan")
    return float(np.sqrt(np.mean(a**2)) * R2D)

rows = []
for variant_name, get_pred in [
    ("V0_baseline",         lambda df,p0,p1,p2: p0),
    ("V1_bias",             lambda df,p0,p1,p2: p1),
    ("V2_bias_lag",         lambda df,p0,p1,p2: p2),
    ("V3_bias_lag_gain",    lambda df,p0,p1,p2: k_gain * p2),
]:
    # accumulate residuals per regime (test only)
    resid_by_regime = {"straight": [], "steady": [], "transient": [], "all": []}
    for (df, p0, p1, p2) in segs_v2:
        pred = get_pred(df, p0, p1, p2)
        meas = df["yaw_rate_meas_rads"].to_numpy()
        n = len(df)
        _, test = train_test_split_idx(n)
        s, st, tr = regime_masks(df)
        resid = pred - meas
        good = np.isfinite(resid) & test
        resid_by_regime["straight"].append(resid[good & s])
        resid_by_regime["steady"].append(resid[good & st])
        resid_by_regime["transient"].append(resid[good & tr])
        resid_by_regime["all"].append(resid[good])
    row = {"variant": variant_name}
    for k_ in ("all","straight","steady","transient"):
        arr = np.concatenate(resid_by_regime[k_]) if resid_by_regime[k_] else np.array([])
        row[f"rmse_degps_{k_}"] = float(np.sqrt(np.mean(arr**2))*R2D) if len(arr) else float("nan")
        row[f"n_{k_}"] = int(len(arr))
    rows.append(row)

res = pd.DataFrame(rows)
res.to_csv(f"{OUT_DIR}/variant_ladder.csv", index=False)
print(res.to_string(index=False))

# Marginal improvement (strict V0->Vlast order on RMSE_all)
base = res.loc[0,"rmse_degps_all"]
print("\nMarginal contributions (RMSE_all, deg/s):", file=sys.stderr)
prev = base
for i in range(1, len(res)):
    cur = res.loc[i,"rmse_degps_all"]
    delta = prev - cur
    pct = 100*delta/base
    print(f"  {res.loc[i,'variant']}: {prev:.4f} -> {cur:.4f}  delta={delta:+.4f} ({pct:+.1f}% of V0)", file=sys.stderr)
    prev = cur

print(f"\nplatform={PLATFORM}  n_segments={len(seg_groups)}  bias_radps={bias:.5f}  k_gain={k_gain:.4f}  median_lag_samples={int(np.median(lags))}", file=sys.stderr)
