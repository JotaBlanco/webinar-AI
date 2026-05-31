"""Compare V0 (pure KS) vs V2 chosen predict for both yaw and XTE-vs-meas."""
import sys, glob, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-07")
sys.path.insert(0, str(ROOT / "final-model"))
from predict import predict, _integrate_traj  # noqa

SIM = ROOT / "data" / "sim" / "segments"
SIM_ONLY = ROOT / "data" / "sim-only" / "segments"
PLATFORMS = ["TESLA_MODEL_3", "FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1", "HYUNDAI_IONIQ_5"]
WHEELBASE = {"TESLA_MODEL_3": 2.875, "FORD_MUSTANG_MACH_E_MK1": 2.984, "FORD_F_150_LIGHTNING_MK1": 3.70, "HYUNDAI_IONIQ_5": 3.0}

def truth_col(d): return "yaw_rate_meas_rads" if "yaw_rate_meas_rads" in d.columns else "psi_dot_rads"

def integ_from_meas(d):
    tcol = truth_col(d)
    t = d["t_s"].to_numpy(float); v = d["v_mps"].to_numpy(float); yr = d[tcol].to_numpy(float)
    n=len(t); psi=np.zeros(n); x=np.zeros(n); y=np.zeros(n)
    for k in range(1,n):
        dt=t[k]-t[k-1]; psi[k]=psi[k-1]+0.5*(yr[k-1]+yr[k])*dt
        pm=0.5*(psi[k-1]+psi[k]); vm=0.5*(v[k-1]+v[k])
        x[k]=x[k-1]+vm*np.cos(pm)*dt; y[k]=y[k-1]+vm*np.sin(pm)*dt
    return x,y

def arclen(x,y):
    dx=np.diff(x); dy=np.diff(y); seg=np.sqrt(dx*dx+dy*dy)
    return np.concatenate([[0.0], np.cumsum(seg)])

def xte(xp,yp,xt,yt,ds=1.0):
    st=arclen(xt,yt); sp=arclen(xp,yp); smax=min(st[-1],sp[-1])
    if smax<5: return None
    sg=np.arange(0,smax,ds)
    return np.sqrt((np.interp(sg,st,xt)-np.interp(sg,sp,xp))**2 + (np.interp(sg,st,yt)-np.interp(sg,sp,yp))**2)

def v0_predict(d, L):
    t = d["t_s"].to_numpy(float); v = d["v_mps"].to_numpy(float); delta = d["delta_road_rad"].to_numpy(float)
    yr = (v/L) * np.tan(delta)
    x,y,_ = _integrate_traj(yr, v, t)
    return yr,x,y

for plat in PLATFORMS:
    files = sorted(glob.glob(str(SIM_ONLY/plat/"*/*/*/sim.csv")))
    nsplit = int(0.8*len(files)); tf = files[nsplit:]
    L = WHEELBASE[plat]
    yaw_v0=0; yaw_v2=0; n_y=0
    xte_v0=0; xte_v2=0; n_x=0
    for sof in tf:
        d_in = pd.read_csv(sof)
        rel = Path(sof).relative_to(SIM_ONLY)
        d_tr = pd.read_csv(SIM/rel)
        tcol = truth_col(d_tr)
        tr_yaw = d_tr[tcol].to_numpy(float)
        # V0
        yr0, x0, y0 = v0_predict(d_in, L)
        # V2 (final)
        pr = predict(d_in, plat)
        yr2 = pr["yaw_rate_pred_rads"].to_numpy(float)
        x2 = pr["x_m"].to_numpy(float); y2 = pr["y_m"].to_numpy(float)
        n = min(len(tr_yaw), len(yr0), len(yr2))
        yaw_v0 += float(np.sum((yr0[:n]-tr_yaw[:n])**2))
        yaw_v2 += float(np.sum((yr2[:n]-tr_yaw[:n])**2))
        n_y += n
        # XTE vs meas truth
        xt,yt = integ_from_meas(d_tr)
        e0 = xte(x0,y0,xt,yt); e2 = xte(x2,y2,xt,yt)
        if e0 is not None and e2 is not None:
            xte_v0 += float(np.sum(e0**2)); xte_v2 += float(np.sum(e2**2)); n_x += len(e0)
    print(f"{plat:30s}  V0_yaw={np.sqrt(yaw_v0/n_y):.5f}  V2_yaw={np.sqrt(yaw_v2/n_y):.5f}  "
          f"V0_XTE={np.sqrt(xte_v0/n_x):.3f}  V2_XTE={np.sqrt(xte_v2/n_x):.3f}")
