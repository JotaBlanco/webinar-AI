"""Baseline V0 + sanity. Loads Mach-E sim CSVs, computes RMSE of
yaw_rate_resid_rads overall and per regime. Prints sign-convention check."""
import glob, os, sys, json
import numpy as np
import pandas as pd

PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
BASE = "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-4/agent-05/data/sim/segments/" + PLATFORM
OUT = "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-4/agent-05/out"
os.makedirs(OUT, exist_ok=True)

paths = sorted(glob.glob(BASE + "/*/*/*/sim.csv"))
# Cap to keep runtime within budget
MAX_SEG = 80
paths = paths[:MAX_SEG]
print(f"Found {len(paths)} segments")

frames = []
for p in paths:
    df = pd.read_csv(p)
    df["__seg__"] = p
    frames.append(df)
D = pd.concat(frames, ignore_index=True)
print("Total samples:", len(D))

# Regime mask per skill doc
delta = D["delta_road_rad"].values
# numerical d-delta/dt on this single (un-segmented) concat would be wrong at boundaries
# compute per-segment then concat masks
groups = D.groupby("__seg__")
ddelta_dt = np.zeros(len(D))
i = 0
for _, g in groups:
    dd = np.gradient(g["delta_road_rad"].values, g["t_s"].values)
    ddelta_dt[i:i+len(g)] = dd
    i += len(g)
D["ddelta_dt"] = ddelta_dt

straight = np.abs(delta) < 0.01
steady = (np.abs(delta) >= 0.01) & (np.abs(ddelta_dt) < 0.05)
transient = (np.abs(delta) >= 0.01) & (np.abs(ddelta_dt) >= 0.05)

def rmse(x):
    x = np.asarray(x)
    x = x[np.isfinite(x)]
    return float(np.sqrt(np.mean(x ** 2))) if len(x) else float("nan")

r = D["yaw_rate_resid_rads"].values
print("\nV0 yaw-rate residual RMSE [rad/s]")
print(f"  overall:   {rmse(r):.5f}  (N={np.isfinite(r).sum()})")
print(f"  straight:  {rmse(r[straight]):.5f}  (N={straight.sum()})")
print(f"  steady:    {rmse(r[steady]):.5f}  (N={steady.sum()})")
print(f"  transient: {rmse(r[transient]):.5f}  (N={transient.sum()})")

# Sign check on cornering
corner = np.abs(delta) >= 0.01
c = np.corrcoef(D["delta_road_rad"].values[corner],
                D["yaw_rate_meas_rads"].values[corner])[0, 1]
print(f"\ncorr(delta_road, yaw_meas) on cornering: {c:+.4f}  (positive expected)")

# Save baseline masks/values for downstream variants
np.savez(os.path.join(OUT, "baseline.npz"),
         t=D["t_s"].values, seg=D["__seg__"].astype("category").cat.codes.values,
         delta_road=D["delta_road_rad"].values,
         v=D["v_mps"].values,
         a_long=D["a_long_mps2"].values,
         a_lat_meas=D["a_lat_meas_mps2"].values,
         yaw_meas=D["yaw_rate_meas_rads"].values,
         yaw_pred=D["yaw_rate_pred_rads"].values,
         yaw_resid=D["yaw_rate_resid_rads"].values,
         ddelta_dt=ddelta_dt,
         straight=straight, steady=steady, transient=transient)
print("\nsaved", os.path.join(OUT, "baseline.npz"))
