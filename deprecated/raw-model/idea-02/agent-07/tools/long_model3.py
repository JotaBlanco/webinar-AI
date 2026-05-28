"""Longitudinal model v3 — clean glitches; richer evaluation.

Changes vs v2:
  * Reject segments with any |a_long| > 15 m/s^2 (clearly bad CAN-decoded IMU).
  * Reject parked segments (v never > 1 m/s) — nothing to learn or evaluate.
  * Tighter integration clamps.
  * Also report per-segment RMSE-distribution AND row-aggregated, both regimes.
"""
import glob, os, json, hashlib
import numpy as np
import pandas as pd

BASE = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-07/data/sim/segments"
OUT  = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-07/out"
os.makedirs(OUT, exist_ok=True)

A_MIN, A_MAX = -6.0, 5.5
V_MIN, V_MAX = 0.0, 45.0
A_GLITCH = 12.0
V_MIN_RUN = 1.0

ford = sorted(glob.glob(f"{BASE}/FORD_*/**/sim.csv", recursive=True))
def load(p):
    d = pd.read_csv(p, usecols=["t_s","v_mps","a_long_mps2","accel_pedal_pct","brake_pressed"]).dropna()
    if len(d) < 100: return None
    d = d.sort_values("t_s").reset_index(drop=True)
    if np.abs(d["a_long_mps2"]).max() > A_GLITCH: return None
    if d["v_mps"].max() < V_MIN_RUN: return None
    return d

segs = [(p,load(p)) for p in ford]
segs = [(p,d) for p,d in segs if d is not None]
print(f"Clean Ford segments: {len(segs)}/{len(ford)}")

def in_train(p):
    return (int(hashlib.md5(p.encode()).hexdigest()[:8],16) % 100) < 70
tr = [(p,d) for p,d in segs if in_train(p)]
te = [(p,d) for p,d in segs if not in_train(p)]
print(f"Train {len(tr)} / Test {len(te)}")

def feats(v,p,b):
    pn = p/100.0; b = b.astype(float)
    return np.stack([
        np.ones_like(v),
        pn, pn*v,
        v, v*np.abs(v),
        b, b*v,
    ], axis=-1)
NAMES = ["1","pedal","pedal*v","v","v|v|","brake","brake*v"]

def XY(segs):
    X,y=[],[]
    for _,d in segs:
        v=d["v_mps"].values; p=d["accel_pedal_pct"].values
        b=d["brake_pressed"].values; a=d["a_long_mps2"].values
        X.append(feats(v,p,b)); y.append(a)
    return np.concatenate(X), np.concatenate(y)

Xtr,ytr = XY(tr)
lam=1.0
theta = np.linalg.solve(Xtr.T@Xtr + lam*np.eye(Xtr.shape[1]), Xtr.T@ytr)
print("theta:")
for n,t in zip(NAMES,theta): print(f"  {n:>10s}: {t:+.5f}")

def arms(segs):
    X,y = XY(segs); return float(np.sqrt(np.mean((X@theta - y)**2)))
print(f"One-step a-RMSE train={arms(tr):.4f}  test={arms(te):.4f} m/s^2")

def pred_a(v,p,b):
    pn=p/100.0
    a = theta[0]+theta[1]*pn+theta[2]*pn*v+theta[3]*v+theta[4]*v*abs(v)+theta[5]*b+theta[6]*b*v
    return float(np.clip(a,A_MIN,A_MAX))

def closed(d, mode):
    t=d["t_s"].values; vm=d["v_mps"].values
    p=d["accel_pedal_pct"].values; b=d["brake_pressed"].values
    aimu=d["a_long_mps2"].values
    n=len(t); v=np.empty(n); v[0]=float(np.clip(vm[0],V_MIN,V_MAX))
    for k in range(n-1):
        dt=t[k+1]-t[k]
        if mode=="imu":
            a=float(np.clip(aimu[k],A_MIN,A_MAX))
        else:
            a=pred_a(v[k],p[k],b[k])
        v[k+1]=float(np.clip(v[k]+a*dt,V_MIN,V_MAX))
    return v

def regimes(d):
    v=d["v_mps"].values; a=d["a_long_mps2"].values
    p=d["accel_pedal_pct"].values; b=d["brake_pressed"].values
    r=np.full(len(v),"other",dtype=object)
    r[(np.abs(a)<0.3)&(v>2)]="cruise"
    r[(a>=0.3)&(p>5)]="accel"
    r[(a<=-0.5)]="brake"
    r[(np.abs(a)<0.3)&(p<2)&(b==0)&(v>2)]="coast"
    return r

rows=[]; per=[]
for path,d in te:
    vm=d["v_mps"].values
    vi=closed(d,"imu"); vp=closed(d,"model")
    reg=regimes(d)
    for name,mask in [("all",np.ones(len(vm),dtype=bool))]+[(r,reg==r) for r in ("cruise","accel","brake","coast","other")]:
        if mask.sum()<5: continue
        rows.append({"regime":name,"n":int(mask.sum()),
                     "rmse_imu":float(np.sqrt(np.mean((vi[mask]-vm[mask])**2))),
                     "rmse_model":float(np.sqrt(np.mean((vp[mask]-vm[mask])**2)))})
    per.append({"path":path,
                "rmse_imu":float(np.sqrt(np.mean((vi-vm)**2))),
                "rmse_model":float(np.sqrt(np.mean((vp-vm)**2)))})

res=pd.DataFrame(rows); ps=pd.DataFrame(per)
ps.to_csv(f"{OUT}/per_segment_rmse_v3.csv", index=False)

def agg(df,r):
    s=df[df["regime"]==r]
    if not len(s): return None
    n=s["n"].sum()
    return {"regime":r, "n_rows":int(n),
            "rmse_imu":  float(np.sqrt((s["n"]*s["rmse_imu"]**2).sum()/n)),
            "rmse_model":float(np.sqrt((s["n"]*s["rmse_model"]**2).sum()/n))}

summary=[agg(res,r) for r in ("all","cruise","accel","brake","coast","other")]
summary=[s for s in summary if s]
print("\n=== Row-weighted RMSE by regime (m/s) — Ford test segments ===")
print(pd.DataFrame(summary).to_string(index=False))

print("\n=== Per-segment RMSE quantiles (test) ===")
for col in ("rmse_imu","rmse_model"):
    q = ps[col].quantile([0.5,0.75,0.9,0.95,1.0])
    print(f"  {col}: median={q[0.5]:.3f}  p75={q[0.75]:.3f}  p90={q[0.9]:.3f}  p95={q[0.95]:.3f}  max={q[1.0]:.3f}")

with open(f"{OUT}/summary_v3.json","w") as f:
    json.dump({"coefficients":dict(zip(NAMES,theta.tolist())),
               "summary":summary,
               "per_seg_quantiles":{
                   "rmse_imu":   ps["rmse_imu"].quantile([.5,.75,.9,.95]).to_dict(),
                   "rmse_model": ps["rmse_model"].quantile([.5,.75,.9,.95]).to_dict()},
               "n_train":len(tr),"n_test":len(te),
               "a_one_step_rmse_test":arms(te)}, f, indent=2)
print("Wrote summary_v3.json")
