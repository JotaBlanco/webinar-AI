"""Local scoring vs sim/segments (with truth available). Compute:
   - yaw RMSE (rad/s)  for V0 and V1
   - distance-resampled CTE RMSE (m) for V0 and V1, vs truth-integrated trajectory
"""
import os, glob, sys
import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-03/final-model")
from predict import predict  # noqa

BASE = "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-03/data/sim/segments"
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]
# Tesla truth = V0 model output, skip


def truth_col(df):
    if "yaw_rate_meas_rads" in df.columns:
        return "yaw_rate_meas_rads"
    if "psi_dot_rads" in df.columns:
        return "psi_dot_rads"
    return None


def integrate_traj(t, v, yaw):
    """Trapezoidal forward-Euler integration of (x, y) given v and yaw_rate."""
    N = len(t)
    dt = np.empty(N); dt[1:] = np.diff(t); dt[0] = dt[1] if N > 1 else 0
    psi = np.zeros(N)
    for k in range(N - 1):
        psi[k + 1] = psi[k] + 0.5 * (yaw[k] + yaw[k + 1]) * dt[k + 1]
    cpsi, spsi = np.cos(psi), np.sin(psi)
    x = np.zeros(N); y = np.zeros(N)
    for k in range(N - 1):
        x[k + 1] = x[k] + 0.5 * (v[k] * cpsi[k] + v[k + 1] * cpsi[k + 1]) * dt[k + 1]
        y[k + 1] = y[k] + 0.5 * (v[k] * spsi[k] + v[k + 1] * spsi[k + 1]) * dt[k + 1]
    return x, y, psi


def cte_resampled(x_t, y_t, x_p, y_p, d_step=1.0):
    """Distance-resample both paths at uniform spacing and report
    cross-track error RMSE — distance from predicted point to truth path.
    Simple proxy: nearest-neighbour distance between resampled paths.
    """
    def resample(x, y, step):
        d = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(x), np.diff(y)))])
        if d[-1] < step:
            return x, y
        s = np.arange(0, d[-1], step)
        return np.interp(s, d, x), np.interp(s, d, y)
    xt, yt = resample(x_t, y_t, d_step)
    xp, yp = resample(x_p, y_p, d_step)
    if len(xt) < 2 or len(xp) < 2:
        return np.nan
    # For each predicted point, nearest truth point distance
    # Vectorised but capped to avoid O(N^2) — sample if too long
    if len(xp) > 2000:
        idx = np.linspace(0, len(xp) - 1, 2000).astype(int)
        xp = xp[idx]; yp = yp[idx]
    # Distance from each pred point to closest truth point
    dx = xp[:, None] - xt[None, :]
    dy = yp[:, None] - yt[None, :]
    d2 = dx * dx + dy * dy
    nn = np.sqrt(d2.min(axis=1))
    return float(np.sqrt(np.mean(nn ** 2)))


def kinematic_v0(t, v, delta, L):
    return (v / L) * np.tan(delta)


rows = []
for plat in PLATFORMS:
    files = glob.glob(os.path.join(BASE, plat, "*", "*", "*", "sim.csv"))
    # subsample for speed
    files = files[::5]
    print(f"{plat}: {len(files)} files (subsampled)", file=sys.stderr)
    L = 3.70 if plat == "FORD_F_150_LIGHTNING_MK1" else (
        2.984 if plat == "FORD_MUSTANG_MACH_E_MK1" else 3.00)
    yaw_v0_sq, yaw_v1_sq, n_yaw = 0.0, 0.0, 0
    cte_v0, cte_v1 = [], []
    for f in files:
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        tc = truth_col(df)
        if tc is None: continue
        t = df["t_s"].to_numpy()
        v = df["v_mps"].to_numpy()
        d = df["delta_road_rad"].to_numpy()
        y_truth = df[tc].to_numpy()

        # V0
        if "yaw_rate_pred_rads" in df.columns:
            y_v0 = df["yaw_rate_pred_rads"].to_numpy()
        else:
            y_v0 = kinematic_v0(t, v, d, L)

        # V1 — strip truth from df then call predict
        df_in = df[["t_s", "delta_wheel_deg", "delta_road_rad", "v_mps",
                    "a_long_mps2"]].copy()
        if "accel_pedal_pct" in df.columns: df_in["accel_pedal_pct"] = df["accel_pedal_pct"]
        if "brake_pressed" in df.columns:   df_in["brake_pressed"]   = df["brake_pressed"]
        df_in["yaw_rate_pred_rads"] = y_v0
        out = predict(df_in, plat)
        y_v1 = out["yaw_rate_pred_rads"].to_numpy()

        m = np.isfinite(y_truth) & np.isfinite(y_v0) & np.isfinite(y_v1)
        yaw_v0_sq += float(np.sum((y_v0[m] - y_truth[m]) ** 2))
        yaw_v1_sq += float(np.sum((y_v1[m] - y_truth[m]) ** 2))
        n_yaw += int(m.sum())

        # Trajectories
        x_t, y_t, _ = integrate_traj(t, v, y_truth)
        x_v0, y_v0t, _ = integrate_traj(t, v, y_v0)
        x_v1, y_v1t, _ = integrate_traj(t, v, y_v1)
        cte_v0.append(cte_resampled(x_t, y_t, x_v0, y_v0t))
        cte_v1.append(cte_resampled(x_t, y_t, x_v1, y_v1t))

    yaw_rmse_v0 = np.sqrt(yaw_v0_sq / n_yaw) if n_yaw else np.nan
    yaw_rmse_v1 = np.sqrt(yaw_v1_sq / n_yaw) if n_yaw else np.nan
    cte_v0_arr = np.array([x for x in cte_v0 if np.isfinite(x)])
    cte_v1_arr = np.array([x for x in cte_v1 if np.isfinite(x)])
    rows.append(dict(platform=plat, n_files=len(files), n_samples=n_yaw,
                     yaw_rmse_v0=yaw_rmse_v0, yaw_rmse_v1=yaw_rmse_v1,
                     cte_rmse_v0=float(np.sqrt(np.mean(cte_v0_arr ** 2))) if len(cte_v0_arr) else np.nan,
                     cte_rmse_v1=float(np.sqrt(np.mean(cte_v1_arr ** 2))) if len(cte_v1_arr) else np.nan))
    print(rows[-1])

pd.DataFrame(rows).to_csv("/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-03/out/local_scores.csv", index=False)
print("Saved local_scores.csv")
