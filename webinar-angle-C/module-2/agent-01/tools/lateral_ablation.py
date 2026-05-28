"""Lateral fidelity variant ladder, scored on FORD_MUSTANG_MACH_E_MK1.

Conventions:
- Residual sign: pred - meas (rule 1)
- delta_road_rad is steering input to the model (rule 3)
- v, delta clamped; lateral states predicted (rule 5)
- Per-platform fits unless stated.
- Train/test split: every 5th sample -> test (rule 7).
"""
import glob, os, json, math
import numpy as np
import pandas as pd

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-2/agent-01"
PATTERN = f"{ROOT}/data/sim/segments/{PLATFORM}/*/*/*/sim.csv"
OUT = f"{ROOT}/out"
os.makedirs(OUT, exist_ok=True)

files = sorted(glob.glob(PATTERN))
print(f"Found {len(files)} segments for {PLATFORM}")

# Load all segments, tag with segment id
frames = []
for f in files:
    seg = "/".join(f.split("/")[-4:-1])
    try:
        df = pd.read_csv(f)
    except Exception as e:
        continue
    needed = {"yaw_rate_pred_rads", "yaw_rate_meas_rads", "v_mps",
              "delta_road_rad", "a_y_pred_mps2", "a_lat_meas_mps2", "t_s"}
    if not needed.issubset(df.columns):
        continue
    if df["yaw_rate_meas_rads"].isna().all():
        continue
    df["segment"] = seg
    frames.append(df)

big = pd.concat(frames, ignore_index=True)
print(f"Concatenated {len(big)} samples from {big['segment'].nunique()} segments")

# --- Sanity: correlation sign (rule 2) -------------------------------------
mask_corner = big["delta_road_rad"].abs() > np.deg2rad(0.5)
corr = np.corrcoef(big.loc[mask_corner, "delta_road_rad"],
                   big.loc[mask_corner, "yaw_rate_meas_rads"])[0, 1]
print(f"corr(delta_road, yaw_rate_meas) on cornering = {corr:+.3f} (expect >0)")

# --- Regime mask -----------------------------------------------------------
# Per-sample mask using a moving-window stability check on delta_road.
big = big.sort_values(["segment", "t_s"]).reset_index(drop=True)
DT = 0.02  # 50 Hz nominal

def add_regimes(df):
    out = []
    for seg, g in df.groupby("segment", sort=False):
        g = g.copy()
        # rate of steering wheel angle (use delta_road_rad)
        ddelta = np.gradient(g["delta_road_rad"].to_numpy())
        g["ddelta"] = ddelta
        # rolling std over ~1s window
        g["delta_std_1s"] = g["delta_road_rad"].rolling(50, min_periods=10, center=True).std().fillna(0)
        out.append(g)
    return pd.concat(out, ignore_index=True)

big = add_regimes(big)

STRAIGHT_DELTA_RAD = np.deg2rad(0.5)
TRANS_DELTA_STD = np.deg2rad(0.3)  # >0.3deg std over 1s = transient

reg_straight = big["delta_road_rad"].abs() < STRAIGHT_DELTA_RAD
reg_transient = (~reg_straight) & (big["delta_std_1s"] > TRANS_DELTA_STD)
reg_steady = (~reg_straight) & (~reg_transient)
big["regime"] = np.where(reg_straight, "straight",
                  np.where(reg_transient, "transient", "steady"))
print("regime counts:", big["regime"].value_counts().to_dict())

# --- Train/test interleaved split -----------------------------------------
big["fold"] = (np.arange(len(big)) % 5 == 0).astype(int)  # 1 = test, 0 = train
test_mask = big["fold"] == 1
train_mask = ~test_mask

# --- Metric -----------------------------------------------------------------
def rmse(x):
    x = np.asarray(x)
    return float(np.sqrt(np.mean(x ** 2)))

def score(pred, meas, regime, mask_subset):
    res = (pred - meas)[mask_subset]
    reg = regime[mask_subset]
    out = {"overall": rmse(res)}
    for r in ["straight", "steady", "transient"]:
        sel = reg == r
        out[r] = rmse(res[sel]) if sel.any() else float("nan")
    return out

yaw_pred0 = big["yaw_rate_pred_rads"].to_numpy()
yaw_meas = big["yaw_rate_meas_rads"].to_numpy()
v = big["v_mps"].to_numpy()
ay_pred0 = big["a_y_pred_mps2"].to_numpy()
ay_meas = big["a_lat_meas_mps2"].to_numpy()
regime = big["regime"].to_numpy()
tr_idx = train_mask.to_numpy()
te_idx = test_mask.to_numpy()

results = {}

# V0: baseline as-is (no preprocessing) -------------------------------------
results["V0_baseline"] = {
    "fit_scope": "n/a",
    "yaw_rate_rads": score(yaw_pred0, yaw_meas, regime, te_idx),
    "a_y_mps2": score(ay_pred0, ay_meas, regime, te_idx),
}

# V1: per-platform constant yaw-rate bias removal (fit on TRAIN) ------------
# bias = median(pred - meas) on TRAIN; subtract bias from pred.
b1 = float(np.median((yaw_pred0 - yaw_meas)[tr_idx]))
yaw_pred1 = yaw_pred0 - b1
ay_pred1 = ay_pred0 - v * b1  # rule 9: a_y = v * psidot, so subtract v*b1
results["V1_yawbias_platform"] = {
    "fit_scope": "per-platform (1 scalar)",
    "param": {"bias_rad_s": b1},
    "yaw_rate_rads": score(yaw_pred1, yaw_meas, regime, te_idx),
    "a_y_mps2": score(ay_pred1, ay_meas, regime, te_idx),
}

# V2: per-platform steering-gain calibration (linear fit) -------------------
# Model: yaw_pred_corr = k * yaw_pred1 (apply on top of V1). Fit on TRAIN.
# This corrects effective gain (steering ratio / wheelbase mismatch).
num = float(np.sum((yaw_pred1[tr_idx]) * yaw_meas[tr_idx]))
den = float(np.sum((yaw_pred1[tr_idx]) ** 2))
k2 = num / den
yaw_pred2 = k2 * yaw_pred1
ay_pred2 = k2 * ay_pred1  # rule 9
results["V2_gain_platform"] = {
    "fit_scope": "per-platform (1 scalar on top of V1)",
    "param": {"k_gain": k2},
    "yaw_rate_rads": score(yaw_pred2, yaw_meas, regime, te_idx),
    "a_y_mps2": score(ay_pred2, ay_meas, regime, te_idx),
}

# V3: per-platform lag alignment (integer-sample shift) ---------------------
# Search shift in [-20, +20] samples (+/-0.4s); choose shift on TRAIN that
# minimises yaw RMSE.  Apply same shift to a_y.
def shift_arr(a, s):
    out = np.full_like(a, np.nan)
    if s == 0:
        out[:] = a
    elif s > 0:
        out[s:] = a[:-s]
    else:
        out[:s] = a[-s:]
    return out

best_s, best_rmse = 0, float("inf")
for s in range(-20, 21):
    shifted = shift_arr(yaw_pred2, s)
    sel = tr_idx & ~np.isnan(shifted)
    r = rmse(shifted[sel] - yaw_meas[sel])
    if r < best_rmse:
        best_rmse, best_s = r, s

yaw_pred3 = shift_arr(yaw_pred2, best_s)
ay_pred3 = shift_arr(ay_pred2, best_s)
# valid mask for V3+ excludes NaNs from shift
valid3 = ~np.isnan(yaw_pred3)
te_idx3 = te_idx & valid3

results["V3_lag_platform"] = {
    "fit_scope": "per-platform (integer shift on top of V2)",
    "param": {"shift_samples": best_s, "shift_s": best_s * DT},
    "yaw_rate_rads": score(yaw_pred3[valid3], yaw_meas[valid3], regime[valid3],
                           te_idx[valid3]),
    "a_y_mps2": score(ay_pred3[valid3], ay_meas[valid3], regime[valid3],
                      te_idx[valid3]),
}

# V4: per-segment yaw-rate bias (CALIBRATION, not model improvement) --------
# Subtract median(pred - meas) on TRAIN per segment.  Re-derive a_y.
yaw_pred4 = yaw_pred3.copy()
ay_pred4 = ay_pred3.copy()
seg_arr = big["segment"].to_numpy()
unique_segs = np.unique(seg_arr)
seg_biases = {}
for s in unique_segs:
    m = (seg_arr == s) & tr_idx & valid3
    if m.sum() < 50:
        continue
    bs = float(np.median(yaw_pred3[m] - yaw_meas[m]))
    seg_biases[s] = bs
    msel = (seg_arr == s) & valid3
    yaw_pred4[msel] = yaw_pred3[msel] - bs
    ay_pred4[msel] = ay_pred3[msel] - v[msel] * bs

results["V4_segbias_segment"] = {
    "fit_scope": "PER-SEGMENT calibration (1 scalar/segment) -- NOT a model improvement",
    "param": {"n_segments": len(seg_biases),
              "median_abs_bias_rad_s": float(np.median([abs(x) for x in seg_biases.values()]))},
    "yaw_rate_rads": score(yaw_pred4[valid3], yaw_meas[valid3], regime[valid3],
                           te_idx[valid3]),
    "a_y_mps2": score(ay_pred4[valid3], ay_meas[valid3], regime[valid3],
                      te_idx[valid3]),
}

# --- Marginal-contribution accounting (strict V0 -> V_last) ---------------
order = ["V0_baseline", "V1_yawbias_platform", "V2_gain_platform",
         "V3_lag_platform", "V4_segbias_segment"]

ladder = []
prev = results["V0_baseline"]["yaw_rate_rads"]["overall"]
for name in order:
    r = results[name]["yaw_rate_rads"]["overall"]
    delta = prev - r
    ladder.append({"variant": name, "yaw_rmse_rad_s": r,
                   "delta_rad_s": delta,
                   "yaw_rmse_deg_s": math.degrees(r),
                   "delta_deg_s": math.degrees(delta)})
    prev = r

with open(f"{OUT}/results.json", "w") as f:
    json.dump({"results": results, "ladder": ladder,
               "n_samples": int(len(big)),
               "n_segments": int(big['segment'].nunique()),
               "corr_delta_yawmeas": corr,
               "regime_counts": big["regime"].value_counts().to_dict()},
              f, indent=2, default=str)

# Pretty print
print("\n=== LADDER (test set, interleaved every-5th) ===")
for row in ladder:
    print(f"{row['variant']:30s} yaw RMSE = {row['yaw_rmse_deg_s']:.4f} deg/s  "
          f"(Delta = {row['delta_deg_s']:+.4f})")

print("\n=== PER-REGIME (deg/s) ===")
for name in order:
    rr = results[name]["yaw_rate_rads"]
    print(f"{name:30s} straight={math.degrees(rr['straight']):.4f} "
          f"steady={math.degrees(rr['steady']):.4f} "
          f"transient={math.degrees(rr['transient']):.4f}")

print("\n=== a_y RMSE (m/s^2) ===")
for name in order:
    rr = results[name]["a_y_mps2"]
    print(f"{name:30s} overall={rr['overall']:.4f} "
          f"straight={rr['straight']:.4f} steady={rr['steady']:.4f} transient={rr['transient']:.4f}")

print("\nParams:")
print(json.dumps({k: v.get("param", {}) for k, v in results.items()}, indent=2, default=str))
