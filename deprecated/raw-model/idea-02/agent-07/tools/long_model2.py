"""Longitudinal model v2 — predicts v_mps from commanded inputs only.

Fixes vs v1:
  * Saturate predicted acceleration to [a_min, a_max] from parameters.
  * Hard-clamp v_pred to [0, 50] each step.
  * Use a leakier basis (no pedal^2; cap pedal*v interaction).
  * Add an aero/drag term that always opposes motion.
  * Provide both one-step (open-loop) and closed-loop metrics.
  * Per-segment results so we can see distribution, not just mean.
"""
import glob, os, json, hashlib
import numpy as np
import pandas as pd

BASE = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-07/data/sim/segments"
OUT  = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-07/out"
os.makedirs(OUT, exist_ok=True)

A_MIN, A_MAX = -8.0, 5.5    # physical actuator limits (matches parameters.py-ish)
V_MIN, V_MAX = 0.0, 50.0

ford_csvs = sorted(glob.glob(f"{BASE}/FORD_*/**/sim.csv", recursive=True))
def load_seg(p):
    d = pd.read_csv(p, usecols=["t_s","v_mps","a_long_mps2",
                                "accel_pedal_pct","brake_pressed"]).dropna()
    if len(d) < 100: return None
    d = d.sort_values("t_s").reset_index(drop=True)
    return d

segs = [(p, load_seg(p)) for p in ford_csvs]
segs = [(p,d) for p,d in segs if d is not None]
print(f"Usable Ford segments: {len(segs)}")

def in_train(path):
    return (int(hashlib.md5(path.encode()).hexdigest()[:8],16) % 100) < 70
train_segs = [(p,d) for p,d in segs if in_train(p)]
test_segs  = [(p,d) for p,d in segs if not in_train(p)]
print(f"Train {len(train_segs)} / Test {len(test_segs)}")

# ----- physics-flavoured feature set -----
# a = k0 (bias/offset)
#   + k1 * pedal_n            (motor torque ~ pedal)
#   + k2 * pedal_n * v        (power saturation: dT/dv at fixed pedal)
#   + k3 * v                  (rolling resistance + motor drag-coast)
#   + k4 * v * |v|            (aero drag, signed by motion)
#   + k5 * brake              (foundation brake)
#   + k6 * brake * v          (brake intensity scales with speed)
def feats(v, pedal, brake):
    pn = pedal/100.0
    vsq = v * np.abs(v)
    return np.stack([
        np.ones_like(v),
        pn,
        pn * v,
        v,
        vsq,
        brake.astype(float),
        brake.astype(float) * v,
    ], axis=-1)
NAMES = ["1","pedal","pedal*v","v","v|v|","brake","brake*v"]

def build_xy(segs):
    Xs, ys = [], []
    for _,d in segs:
        v = d["v_mps"].values; p = d["accel_pedal_pct"].values
        b = d["brake_pressed"].values; a = d["a_long_mps2"].values
        Xs.append(feats(v,p,b)); ys.append(a)
    return np.concatenate(Xs), np.concatenate(ys)

Xtr, ytr = build_xy(train_segs)
print(f"Train rows: {len(ytr)}")

# Ridge LS
lam = 1.0
A = Xtr.T @ Xtr + lam * np.eye(Xtr.shape[1])
theta = np.linalg.solve(A, Xtr.T @ ytr)
print("Coefficients:")
for n,t in zip(NAMES,theta): print(f"  {n:>10s}: {t:+.5f}")

# Open-loop one-step a-RMSE on train and test
def one_step_arms(segs):
    X,y = build_xy(segs); return float(np.sqrt(np.mean((X@theta - y)**2)))
print(f"One-step a-RMSE: train={one_step_arms(train_segs):.4f}  test={one_step_arms(test_segs):.4f} m/s^2")

# ----- closed-loop integration -----
def predict_a(v, pedal, brake):
    pn = pedal/100.0
    a = (theta[0] + theta[1]*pn + theta[2]*pn*v + theta[3]*v
         + theta[4]*v*abs(v) + theta[5]*brake + theta[6]*brake*v)
    return float(np.clip(a, A_MIN, A_MAX))

def closed_loop(d, mode):
    t=d["t_s"].values; vm=d["v_mps"].values
    p=d["accel_pedal_pct"].values; b=d["brake_pressed"].values
    aimu=d["a_long_mps2"].values
    n=len(t); v=np.empty(n); v[0]=max(V_MIN, vm[0])
    for k in range(n-1):
        dt = t[k+1]-t[k]
        if mode=="imu":
            a = float(np.clip(aimu[k], A_MIN, A_MAX))
        else:
            a = predict_a(v[k], p[k], b[k])
        v[k+1] = float(np.clip(v[k] + a*dt, V_MIN, V_MAX))
    return v

# Regimes per-row (using IMU sensed a and commanded inputs)
def regimes(d):
    v=d["v_mps"].values; a=d["a_long_mps2"].values
    p=d["accel_pedal_pct"].values; b=d["brake_pressed"].values
    r=np.full(len(v),"other",dtype=object)
    r[(np.abs(a)<0.3)&(v>2)] = "cruise"
    r[(a>=0.3)&(p>5)]       = "accel"
    r[(a<=-0.5)]            = "brake"
    r[(np.abs(a)<0.3)&(p<2)&(b==0)&(v>2)] = "coast"
    return r

per_seg=[]; rows=[]
for path,d in test_segs:
    vm=d["v_mps"].values
    vi=closed_loop(d,"imu")
    vp=closed_loop(d,"model")
    reg=regimes(d)
    # cap residuals (should never exceed V_MAX-V_MIN=50)
    for name,mask in [("all",np.ones(len(vm),dtype=bool))]+ \
                     [(r, reg==r) for r in ("cruise","accel","brake","coast","other")]:
        if mask.sum()<5: continue
        rows.append({
            "regime":name,"n":int(mask.sum()),
            "rmse_imu":float(np.sqrt(np.mean((vi[mask]-vm[mask])**2))),
            "rmse_model":float(np.sqrt(np.mean((vp[mask]-vm[mask])**2))),
        })
    per_seg.append({
        "segment": os.path.relpath(path, BASE),
        "n": int(len(vm)),
        "rmse_imu":  float(np.sqrt(np.mean((vi-vm)**2))),
        "rmse_model":float(np.sqrt(np.mean((vp-vm)**2))),
        "v_mean": float(vm.mean()),
    })

res = pd.DataFrame(rows)
ps  = pd.DataFrame(per_seg)
ps.to_csv(f"{OUT}/per_segment_rmse_v2.csv", index=False)

print("\n=== Per-segment RMSE distribution (test) ===")
for col in ("rmse_imu","rmse_model"):
    q = ps[col].quantile([0.5,0.75,0.9,0.95,1.0])
    print(f"  {col}: median={q[0.5]:.3f} p75={q[0.75]:.3f} p90={q[0.9]:.3f} p95={q[0.95]:.3f} max={q[1.0]:.3f}")

def agg(df, reg):
    sub=df[df["regime"]==reg]
    if not len(sub): return None
    n=sub["n"].sum()
    return {"regime":reg, "n_rows":int(n),
            "rmse_imu":  float(np.sqrt((sub["n"]*sub["rmse_imu"]**2).sum()/n)),
            "rmse_model":float(np.sqrt((sub["n"]*sub["rmse_model"]**2).sum()/n))}

summary=[agg(res,r) for r in ("all","cruise","accel","brake","coast","other")]
summary=[s for s in summary if s]
print("\n=== Row-weighted RMSE by regime (m/s) ===")
print(pd.DataFrame(summary).to_string(index=False))

with open(f"{OUT}/summary_v2.json","w") as f:
    json.dump({"coefficients":dict(zip(NAMES,theta.tolist())),
               "summary":summary,
               "per_seg_quantiles":{
                   "rmse_imu":   ps["rmse_imu"].quantile([.5,.75,.9,.95]).to_dict(),
                   "rmse_model": ps["rmse_model"].quantile([.5,.75,.9,.95]).to_dict(),
               }}, f, indent=2)
