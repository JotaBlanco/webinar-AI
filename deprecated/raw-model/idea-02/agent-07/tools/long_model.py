"""Longitudinal model that predicts v_mps without consuming measured v as input.

Setup
-----
Each Ford segment provides 50 Hz traces of:
  t_s, v_mps (truth target), a_long_mps2 (IMU sensed),
  accel_pedal_pct (commanded), brake_pressed (commanded binary).

Models
------
B0_imu  : closed-loop integration of *sensed* a_long.  v_{k+1} = v_k + a_imu * dt.
          Sanity baseline. Uses sensed acceleration (still no measured v
          feedback). Initial v_0 = v_meas[0].

M1_pedal: closed-loop integration of acceleration predicted from a fitted
          longitudinal-dynamics map: a_hat = f(v, accel_pedal_pct, brake_pressed).
          Uses ONLY commanded inputs + current state v_k + initial v_0.
          Fitted with linear least squares over a polynomial feature set.

We split segments (not rows) train/test 70/30 by hashing, fit on train,
report closed-loop RMSE on test by regime.
"""
import glob, os, json, hashlib
import numpy as np
import pandas as pd

BASE = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-07/data/sim/segments"
OUT  = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-07/out"
os.makedirs(OUT, exist_ok=True)

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------
ford_csvs = sorted(glob.glob(f"{BASE}/FORD_*/**/sim.csv", recursive=True))
print(f"Found {len(ford_csvs)} Ford segments")

def load_seg(path):
    d = pd.read_csv(path, usecols=["t_s","v_mps","a_long_mps2",
                                   "accel_pedal_pct","brake_pressed"])
    # robust ordering and dt
    d = d.sort_values("t_s").reset_index(drop=True)
    # drop trailing NaNs
    d = d.dropna().reset_index(drop=True)
    if len(d) < 50:
        return None
    return d

segs = []
for p in ford_csvs:
    d = load_seg(p)
    if d is not None:
        segs.append((p, d))
print(f"Usable segments: {len(segs)}")

# 70/30 split by segment-path hash
def in_train(path):
    h = int(hashlib.md5(path.encode()).hexdigest()[:8], 16)
    return (h % 100) < 70

train_segs = [(p,d) for p,d in segs if in_train(p)]
test_segs  = [(p,d) for p,d in segs if not in_train(p)]
print(f"Train: {len(train_segs)}  Test: {len(test_segs)}")

# ---------------------------------------------------------------------------
# Feature engineering for a_hat = f(v, accel_pct, brake)
# ---------------------------------------------------------------------------
# We choose a physics-flavoured feature set:
#   bias, v, v^2  (drag, rolling-resistance, idle torque)
#   pedal, pedal*v, pedal^2
#   brake, brake*v
def feats(v, pedal, brake):
    pedal_n = pedal / 100.0  # 0..1
    return np.stack([
        np.ones_like(v),
        v,
        v**2,
        pedal_n,
        pedal_n * v,
        pedal_n**2,
        brake.astype(float),
        brake.astype(float) * v,
    ], axis=-1)

FEATURE_NAMES = ["1","v","v^2","pedal","pedal*v","pedal^2","brake","brake*v"]

def build_xy(segs):
    Xs, ys = [], []
    for _,d in segs:
        v = d["v_mps"].values
        p = d["accel_pedal_pct"].values
        b = d["brake_pressed"].values
        a = d["a_long_mps2"].values  # IMU truth for acceleration
        Xs.append(feats(v,p,b))
        ys.append(a)
    return np.concatenate(Xs), np.concatenate(ys)

Xtr, ytr = build_xy(train_segs)
print(f"Train rows: {len(ytr)}")

# Ridge regression for stability
lam = 1e-3 * len(ytr)
A = Xtr.T @ Xtr + lam * np.eye(Xtr.shape[1])
b = Xtr.T @ ytr
theta = np.linalg.solve(A, b)

print("Coefficients (a [m/s^2] ~ feature sum):")
for n, t in zip(FEATURE_NAMES, theta):
    print(f"  {n:>8s}: {t:+.5f}")

# Open-loop one-step a-residual RMSE (sanity)
yhat_tr = Xtr @ theta
print(f"Train acc-RMSE (one-step a residual): {np.sqrt(np.mean((yhat_tr-ytr)**2)):.4f} m/s^2")

# ---------------------------------------------------------------------------
# Closed-loop integration on test segments
# ---------------------------------------------------------------------------
def predict_a(v, pedal, brake, theta):
    f = feats(np.array([v]), np.array([pedal]), np.array([brake]))
    return float(f @ theta)

def closed_loop(d, mode, theta=None):
    """Returns array of predicted v_mps over the segment (same length as d).
    mode='imu'   : integrate measured a_long
    mode='model' : integrate model-predicted a_hat (commanded inputs only)
    Initial v_0 = measured v_mps[0]."""
    t = d["t_s"].values
    v_meas = d["v_mps"].values
    pedal = d["accel_pedal_pct"].values
    brake = d["brake_pressed"].values
    a_imu = d["a_long_mps2"].values
    n = len(t)
    v = np.empty(n)
    v[0] = v_meas[0]
    for k in range(n-1):
        dt = t[k+1]-t[k]
        if mode == "imu":
            a = a_imu[k]
        elif mode == "model":
            a = predict_a(v[k], pedal[k], brake[k], theta)
        else:
            raise ValueError(mode)
        v[k+1] = max(0.0, v[k] + a * dt)  # physical floor at 0
    return v

# Per-segment RMSE, plus regime classification per-row, then segment-level rmse.
def classify_rows(d):
    """Return regime per row: cruise, accel, brake, coast."""
    v = d["v_mps"].values
    p = d["accel_pedal_pct"].values
    b = d["brake_pressed"].values
    a = d["a_long_mps2"].values
    reg = np.full(len(v), "other", dtype=object)
    # cruise: low |a| and moderate speed
    reg[(np.abs(a) < 0.3) & (v > 2.0)] = "cruise"
    reg[(a >= 0.3) & (p > 5)] = "accel"
    reg[(a <= -0.5)] = "brake"  # captures regen + foundation
    reg[(np.abs(a) < 0.3) & (p < 2) & (b == 0) & (v > 2)] = "coast"
    return reg

results = []
for path, d in test_segs:
    v_meas = d["v_mps"].values
    v_imu  = closed_loop(d, "imu")
    v_mod  = closed_loop(d, "model", theta=theta)
    # RMSE per regime
    reg = classify_rows(d)
    for name, mask in [("all", np.ones(len(v_meas),dtype=bool))] + \
                       [(r, reg==r) for r in ("cruise","accel","brake","coast","other")]:
        if mask.sum() < 5: continue
        results.append({
            "segment": os.path.relpath(path, BASE),
            "regime": name,
            "n": int(mask.sum()),
            "rmse_imu":   float(np.sqrt(np.mean((v_imu[mask]-v_meas[mask])**2))),
            "rmse_model": float(np.sqrt(np.mean((v_mod[mask]-v_meas[mask])**2))),
        })

res_df = pd.DataFrame(results)
res_df.to_csv(f"{OUT}/per_segment_rmse.csv", index=False)

# Aggregate (row-weighted)
def agg(df, regime):
    sub = df[df["regime"]==regime]
    if len(sub)==0: return None
    n = sub["n"].sum()
    # combine via sqrt(sum(n*rmse^2)/sum(n))
    rmse_imu = np.sqrt((sub["n"]*sub["rmse_imu"]**2).sum()/n)
    rmse_mod = np.sqrt((sub["n"]*sub["rmse_model"]**2).sum()/n)
    return {"regime":regime, "n_rows":int(n),
            "rmse_imu":float(rmse_imu), "rmse_model":float(rmse_mod)}

summary = [agg(res_df, r) for r in ("all","cruise","accel","brake","coast","other")]
summary = [s for s in summary if s]
print("\n=== Closed-loop RMSE on test segments (m/s) ===")
print(pd.DataFrame(summary).to_string(index=False))

with open(f"{OUT}/summary.json","w") as f:
    json.dump({"coefficients":dict(zip(FEATURE_NAMES, theta.tolist())),
               "summary":summary,
               "n_train_segs":len(train_segs),
               "n_test_segs":len(test_segs)}, f, indent=2)
print(f"\nWrote {OUT}/summary.json and {OUT}/per_segment_rmse.csv")
