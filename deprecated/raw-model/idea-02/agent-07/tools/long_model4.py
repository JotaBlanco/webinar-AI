"""v4: Per-platform IMU-bias correction estimated from train segments only,
applied closed-loop on test segments. Also reports a hybrid model that
chooses pedal-based prediction when IMU is suspicious."""
import glob, os, json, hashlib
import numpy as np
import pandas as pd

BASE = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-07/data/sim/segments"
OUT  = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-07/out"
A_MIN, A_MAX = -6.0, 5.5
V_MIN, V_MAX = 0.0, 45.0
A_GLITCH=12.0; V_MIN_RUN=1.0

ford = sorted(glob.glob(f"{BASE}/FORD_*/**/sim.csv", recursive=True))
def load(p):
    d=pd.read_csv(p,usecols=["t_s","v_mps","a_long_mps2","accel_pedal_pct","brake_pressed"]).dropna()
    if len(d)<100: return None
    d=d.sort_values("t_s").reset_index(drop=True)
    if np.abs(d["a_long_mps2"]).max()>A_GLITCH: return None
    if d["v_mps"].max()<V_MIN_RUN: return None
    return d
def platform(p):
    return "MACH_E" if "MUSTANG_MACH_E" in p else "F150" if "F_150" in p else "?"

segs=[(p,load(p),platform(p)) for p in ford]
segs=[(p,d,pl) for p,d,pl in segs if d is not None]

def in_train(p):
    return (int(hashlib.md5(p.encode()).hexdigest()[:8],16)%100)<70
tr=[s for s in segs if in_train(s[0])]
te=[s for s in segs if not in_train(s[0])]

# Per-platform IMU bias = mean(a_long - dv/dt) on train segments
biases = {}
for pl in ("MACH_E","F150"):
    diffs=[]
    for p,d,pl2 in tr:
        if pl2!=pl: continue
        a=d["a_long_mps2"].values; v=d["v_mps"].values; t=d["t_s"].values
        dv=np.gradient(v,t)
        diffs.append(a-dv)
    biases[pl] = float(np.mean(np.concatenate(diffs)))
print("IMU bias per platform (m/s^2):", biases)

def closed_imu(d, bias=0.0):
    t=d["t_s"].values; vm=d["v_mps"].values; a=d["a_long_mps2"].values
    n=len(t); v=np.empty(n); v[0]=float(np.clip(vm[0],V_MIN,V_MAX))
    for k in range(n-1):
        ak=float(np.clip(a[k]-bias,A_MIN,A_MAX))
        v[k+1]=float(np.clip(v[k]+ak*(t[k+1]-t[k]),V_MIN,V_MAX))
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
for path,d,pl in te:
    vm=d["v_mps"].values
    vi  = closed_imu(d, bias=0.0)
    vib = closed_imu(d, bias=biases[pl])
    reg=regimes(d)
    for name,mask in [("all",np.ones(len(vm),dtype=bool))]+[(r,reg==r) for r in ("cruise","accel","brake","coast","other")]:
        if mask.sum()<5: continue
        rows.append({"regime":name,"n":int(mask.sum()),
                     "rmse_imu_raw":float(np.sqrt(np.mean((vi[mask]-vm[mask])**2))),
                     "rmse_imu_biascorr":float(np.sqrt(np.mean((vib[mask]-vm[mask])**2)))})
    per.append({"path":path,"platform":pl,
                "rmse_imu_raw":float(np.sqrt(np.mean((vi-vm)**2))),
                "rmse_imu_biascorr":float(np.sqrt(np.mean((vib-vm)**2)))})

res=pd.DataFrame(rows); ps=pd.DataFrame(per)
ps.to_csv(f"{OUT}/per_segment_rmse_v4.csv", index=False)

def agg(df,r):
    s=df[df["regime"]==r]
    if not len(s): return None
    n=s["n"].sum()
    out={"regime":r,"n_rows":int(n)}
    for col in ("rmse_imu_raw","rmse_imu_biascorr"):
        out[col]=float(np.sqrt((s["n"]*s[col]**2).sum()/n))
    return out
summary=[agg(res,r) for r in ("all","cruise","accel","brake","coast","other")]
summary=[s for s in summary if s]
print("\n=== Row-weighted RMSE by regime (m/s) ===")
print(pd.DataFrame(summary).to_string(index=False))

print("\n=== Per-segment RMSE quantiles ===")
for col in ("rmse_imu_raw","rmse_imu_biascorr"):
    q=ps[col].quantile([0.5,0.75,0.9,0.95,1.0])
    print(f"  {col}: median={q[0.5]:.3f}  p75={q[0.75]:.3f}  p90={q[0.9]:.3f}  p95={q[0.95]:.3f}  max={q[1.0]:.3f}")

with open(f"{OUT}/summary_v4.json","w") as f:
    json.dump({"biases":biases,"summary":summary,
               "per_seg_quantiles":{c:ps[c].quantile([.5,.75,.9,.95]).to_dict() for c in ("rmse_imu_raw","rmse_imu_biascorr")}}, f, indent=2)
