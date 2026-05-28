"""Plot a handful of test segments to eyeball model vs IMU vs truth."""
import glob, os, hashlib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-07/data/sim/segments"
OUT  = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-07/out"

# Re-derive theta and biases the same way (kept simple, duplication on purpose)
A_MIN,A_MAX = -6.0,5.5; V_MIN,V_MAX=0.0,45.0; A_GLITCH=12.0; V_MIN_RUN=1.0
ford=sorted(glob.glob(f"{BASE}/FORD_*/**/sim.csv",recursive=True))
def load(p):
    d=pd.read_csv(p,usecols=["t_s","v_mps","a_long_mps2","accel_pedal_pct","brake_pressed"]).dropna()
    if len(d)<100: return None
    d=d.sort_values("t_s").reset_index(drop=True)
    if np.abs(d["a_long_mps2"]).max()>A_GLITCH: return None
    if d["v_mps"].max()<V_MIN_RUN: return None
    return d
segs=[(p,load(p)) for p in ford]; segs=[(p,d) for p,d in segs if d is not None]
def in_train(p): return (int(hashlib.md5(p.encode()).hexdigest()[:8],16)%100)<70
tr=[(p,d) for p,d in segs if in_train(p)]; te=[(p,d) for p,d in segs if not in_train(p)]

def feats(v,p,b):
    pn=p/100.0; b=b.astype(float)
    return np.stack([np.ones_like(v),pn,pn*v,v,v*np.abs(v),b,b*v],axis=-1)
X=[]; y=[]
for _,d in tr:
    X.append(feats(d["v_mps"].values,d["accel_pedal_pct"].values,d["brake_pressed"].values))
    y.append(d["a_long_mps2"].values)
X=np.concatenate(X); y=np.concatenate(y)
theta=np.linalg.solve(X.T@X+np.eye(7),X.T@y)

def pred_a(v,p,b):
    pn=p/100.0
    a=theta[0]+theta[1]*pn+theta[2]*pn*v+theta[3]*v+theta[4]*v*abs(v)+theta[5]*b+theta[6]*b*v
    return float(np.clip(a,A_MIN,A_MAX))

def closed(d,mode):
    t=d["t_s"].values; vm=d["v_mps"].values
    p=d["accel_pedal_pct"].values; b=d["brake_pressed"].values
    aimu=d["a_long_mps2"].values
    n=len(t); v=np.empty(n); v[0]=float(np.clip(vm[0],V_MIN,V_MAX))
    for k in range(n-1):
        dt=t[k+1]-t[k]
        a=float(np.clip(aimu[k],A_MIN,A_MAX)) if mode=="imu" else pred_a(v[k],p[k],b[k])
        v[k+1]=float(np.clip(v[k]+a*dt,V_MIN,V_MAX))
    return v

# Pick 4 test segments at different RMSEs.
import random; random.seed(7)
pick = random.sample(te, 6)
fig,axes=plt.subplots(3,2,figsize=(12,9))
for ax,(path,d) in zip(axes.ravel(),pick):
    t=d["t_s"].values; vm=d["v_mps"].values
    vi=closed(d,"imu"); vp=closed(d,"model")
    ax.plot(t,vm,"k-",lw=1.5,label="v_meas (truth)")
    ax.plot(t,vi,"b-",lw=1.0,label="IMU-integrate")
    ax.plot(t,vp,"r-",lw=1.0,label="pedal-model")
    ax.set_title(os.path.basename(os.path.dirname(os.path.dirname(path)))[:20]+f"  rmse_imu={np.sqrt(np.mean((vi-vm)**2)):.2f}  rmse_mod={np.sqrt(np.mean((vp-vm)**2)):.2f}")
    ax.set_xlabel("t [s]"); ax.set_ylabel("v [m/s]")
    ax.legend(fontsize=7)
fig.tight_layout(); fig.savefig(f"{OUT}/example_segments.png",dpi=120)
print("Wrote",f"{OUT}/example_segments.png")
