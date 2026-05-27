"""Diagnostic: predicted vs truth scatter, plus per-speed-bin RMSE."""
import numpy as np, pandas as pd
from pathlib import Path

SIM_ROOT = Path(__file__).resolve().parents[1] / "data" / "sim" / "segments" / "TESLA_MODEL_3"
OUT = Path(__file__).resolve().parents[1] / "out"

L=2.875; TRACK=1.580; G=9.81

def truth(df):
    v_rl=df["wheel_RL_kph"].to_numpy()/3.6
    v_rr=df["wheel_RR_kph"].to_numpy()/3.6
    return (v_rl-v_rr)/TRACK

csvs = sorted(SIM_ROOT.glob("*/*/*/sim.csv"))[::8][:120]
all_v, all_y, all_pks, all_pfull = [], [], [], []
alpha=0.8657; Ku=0.0060; tau=0.10
from scipy.signal import butter, filtfilt

for p in csvs:
    df = pd.read_csv(p)
    if "wheel_RL_kph" not in df.columns: continue
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    y = truth(df)
    pks   = v*np.tan(delta)/L
    pfull = v*np.tan(alpha*delta) / (L*(1+Ku*v*v/(G*L)))
    dt = float(df["t_s"].iloc[1]-df["t_s"].iloc[0])
    fc = 1.0/(2*np.pi*tau); b,a = butter(2, fc/(0.5/dt))
    pfull = filtfilt(b,a,pfull)
    m = (v>=5) & (np.abs(y)>=np.deg2rad(2))
    all_v.append(v[m]); all_y.append(y[m]); all_pks.append(pks[m]); all_pfull.append(pfull[m])

v=np.concatenate(all_v); y=np.concatenate(all_y); pks=np.concatenate(all_pks); pfull=np.concatenate(all_pfull)
print(f"N samples activity-masked = {len(y)}")
print(f"std(y_truth) = {np.degrees(np.std(y)):.3f} deg/s  (signal level)")
print(f"baseline RMSE = {np.degrees(np.sqrt(np.mean((pks-y)**2))):.3f} deg/s")
print(f"full     RMSE = {np.degrees(np.sqrt(np.mean((pfull-y)**2))):.3f} deg/s")
print(f"baseline R^2  = {1 - np.var(pks-y)/np.var(y):.4f}")
print(f"full     R^2  = {1 - np.var(pfull-y)/np.var(y):.4f}")
print()
# Per-speed-bin RMSE
bins = [5,10,15,20,25,30,40]
print("speed_bin    n     RMSE_base   RMSE_full   improvement")
for i in range(len(bins)-1):
    lo,hi = bins[i], bins[i+1]
    mm = (v>=lo)&(v<hi)
    if mm.sum() < 100: continue
    rb = np.degrees(np.sqrt(np.mean((pks[mm]-y[mm])**2)))
    rf = np.degrees(np.sqrt(np.mean((pfull[mm]-y[mm])**2)))
    print(f"  {lo:3d}-{hi:3d}  {mm.sum():6d}   {rb:6.2f}      {rf:6.2f}      {rb-rf:+.2f}")

# Examine extreme-error cases (where ks vastly overshoots truth) — those drive RMSE
err = pks - y
big = np.argsort(np.abs(err))[-20:]
print("\nWorst 20 baseline-error samples:")
print(f"  median |truth| there: {np.degrees(np.median(np.abs(y[big]))):.2f}, "
      f"median |pred|: {np.degrees(np.median(np.abs(pks[big]))):.2f}, "
      f"median v: {np.median(v[big]):.1f} m/s")
