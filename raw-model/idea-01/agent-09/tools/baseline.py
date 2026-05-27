"""Compute baseline lateral prediction error from existing Ford sim CSVs."""
import glob
import os
import numpy as np
import pandas as pd

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-09/data/sim/segments"

def metrics(df):
    # residual columns are pred - meas (we'll recompute to be sure)
    yaw_meas = df["yaw_rate_meas_rads"].values
    yaw_pred = df["yaw_rate_pred_rads"].values
    ay_meas = df["a_lat_meas_mps2"].values
    ay_pred = df["a_y_pred_mps2"].values
    # mask to driving (speed > 2 m/s) — KS yaw rate = (v/L) tan(delta) goes to zero at standstill
    v = df["v_mps"].values
    m = v > 2.0
    if m.sum() < 50:
        return None
    res_yaw = yaw_pred[m] - yaw_meas[m]
    res_ay = ay_pred[m] - ay_meas[m]
    return {
        "n": int(m.sum()),
        "rmse_yaw": float(np.sqrt(np.mean(res_yaw**2))),
        "mae_yaw": float(np.mean(np.abs(res_yaw))),
        "bias_yaw": float(np.mean(res_yaw)),
        "rmse_ay": float(np.sqrt(np.mean(res_ay**2))),
        "bias_ay": float(np.mean(res_ay)),
        "std_yaw_meas": float(np.std(yaw_meas[m])),
        "mean_v": float(np.mean(v[m])),
    }

rows = []
for plat in ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"]:
    for csv in sorted(glob.glob(os.path.join(ROOT, plat, "*", "*", "*", "sim.csv"))):
        try:
            df = pd.read_csv(csv)
        except Exception as e:
            continue
        m = metrics(df)
        if m is None: continue
        m["plat"] = plat
        m["seg"] = csv
        rows.append(m)

if not rows:
    print("no rows")
else:
    df = pd.DataFrame(rows)
    print(f"n segments: {len(df)}")
    for plat, g in df.groupby("plat"):
        # weighted aggregate by sample count
        n = g["n"].sum()
        wmse_yaw = (g["rmse_yaw"]**2 * g["n"]).sum() / n
        wmse_ay  = (g["rmse_ay" ]**2 * g["n"]).sum() / n
        print(f"\n{plat}: {len(g)} segs, {n} samples")
        print(f"  yaw RMSE (pooled): {np.sqrt(wmse_yaw):.5f} rad/s")
        print(f"  yaw bias  (mean):  {(g['bias_yaw']*g['n']).sum()/n:+.5f} rad/s")
        print(f"  ay  RMSE (pooled): {np.sqrt(wmse_ay):.4f} m/s^2")
        print(f"  ay  bias  (mean):  {(g['bias_ay'] *g['n']).sum()/n:+.4f} m/s^2")
    # All Ford pooled
    n = df["n"].sum()
    wmse_yaw = (df["rmse_yaw"]**2 * df["n"]).sum() / n
    wmse_ay  = (df["rmse_ay" ]**2 * df["n"]).sum() / n
    print(f"\nALL FORD POOLED: {n} samples")
    print(f"  yaw RMSE: {np.sqrt(wmse_yaw):.5f} rad/s")
    print(f"  yaw bias: {(df['bias_yaw']*df['n']).sum()/n:+.5f} rad/s")
    print(f"  ay  RMSE: {np.sqrt(wmse_ay):.4f} m/s^2")
    df.to_csv("/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-09/out/baseline_per_seg.csv", index=False)
