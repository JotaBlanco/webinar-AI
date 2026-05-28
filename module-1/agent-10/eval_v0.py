"""Evaluation of V0 baseline on Ford platforms.

For each Ford segment we have `yaw_rate_pred_rads` (V0 KS) and `yaw_rate_meas_rads` (truth).
We compute:
  1) Yaw rate RMSE (rad/s)
  2) Distance-resampled cross-track error RMSE (m). Truth trajectory is
     integrated from measured yaw rate + measured velocity (single-track integration).
     V0 trajectory is integrated from `yaw_rate_pred_rads` using the same velocity.
"""
import os
import sys
import glob
import numpy as np
import pandas as pd

DATA_ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/data/sim/segments"
FORD_PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1"]


def integrate_trajectory(t, v, yaw_rate, psi0=0.0, x0=0.0, y0=0.0):
    """Trapezoidal/forward Euler integration of (v, psi_dot) -> (x, y, psi)."""
    n = len(t)
    psi = np.empty(n)
    x = np.empty(n)
    y = np.empty(n)
    psi[0] = psi0
    x[0] = x0
    y[0] = y0
    for k in range(n - 1):
        dt = t[k + 1] - t[k]
        # Use midpoint heading for better accuracy on the position step
        psi_mid = psi[k] + 0.5 * dt * yaw_rate[k]
        v_mid = 0.5 * (v[k] + v[k + 1])
        x[k + 1] = x[k] + v_mid * np.cos(psi_mid) * dt
        y[k + 1] = y[k] + v_mid * np.sin(psi_mid) * dt
        psi[k + 1] = psi[k] + dt * 0.5 * (yaw_rate[k] + yaw_rate[k + 1])
    return x, y, psi


def cte_rmse_distance_resampled(t, v, yaw_true, yaw_pred, ds=1.0):
    """Cross-track error RMSE between truth and predicted trajectories,
    sampled at uniform arc length ds (default 1 m) along the truth path."""
    x_t, y_t, _ = integrate_trajectory(t, v, yaw_true)
    x_p, y_p, _ = integrate_trajectory(t, v, yaw_pred)

    # Truth arc length
    dx = np.diff(x_t)
    dy = np.diff(y_t)
    seg = np.hypot(dx, dy)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    s_total = s[-1]
    if s_total < ds * 5:  # too short to be meaningful
        return None

    s_grid = np.arange(0.0, s_total, ds)
    # Interpolate truth and prediction positions by arc-length-of-truth.
    x_t_g = np.interp(s_grid, s, x_t)
    y_t_g = np.interp(s_grid, s, y_t)
    x_p_g = np.interp(s_grid, s, x_p)
    y_p_g = np.interp(s_grid, s, y_p)
    # CTE: euclidean distance between the two interpolated points
    err = np.hypot(x_t_g - x_p_g, y_t_g - y_p_g)
    return float(np.sqrt(np.mean(err ** 2)))


def yaw_rmse(yaw_true, yaw_pred):
    return float(np.sqrt(np.mean((yaw_true - yaw_pred) ** 2)))


def find_segments(platform, limit=None):
    pattern = os.path.join(DATA_ROOT, platform, "**", "sim.csv")
    paths = sorted(glob.glob(pattern, recursive=True))
    if limit:
        paths = paths[:limit]
    return paths


def score_segment(csv_path, yaw_pred_col="yaw_rate_pred_rads"):
    df = pd.read_csv(csv_path)
    t = df["t_s"].to_numpy()
    v = df["v_mps"].to_numpy()
    yaw_true = df["yaw_rate_meas_rads"].to_numpy()
    yaw_pred = df[yaw_pred_col].to_numpy()
    if len(t) < 50:
        return None
    if np.any(~np.isfinite(yaw_true)) or np.any(~np.isfinite(yaw_pred)):
        return None
    return {
        "n": len(t),
        "yaw_rmse": yaw_rmse(yaw_true, yaw_pred),
        "cte_rmse": cte_rmse_distance_resampled(t, v, yaw_true, yaw_pred),
        "path": csv_path,
    }


def main(limit=None):
    rows = []
    for plat in FORD_PLATFORMS:
        paths = find_segments(plat, limit=limit)
        print(f"[{plat}] {len(paths)} segments", file=sys.stderr)
        for p in paths:
            try:
                r = score_segment(p)
            except Exception as e:
                print(f"  ! {p}: {e}", file=sys.stderr)
                continue
            if r is None:
                continue
            r["platform"] = plat
            rows.append(r)
    df = pd.DataFrame(rows)
    # Per-platform aggregates
    for plat, sub in df.groupby("platform"):
        cte = sub["cte_rmse"].dropna()
        print(f"\n[{plat}] n={len(sub)}  yaw_rmse mean={sub['yaw_rmse'].mean():.4f}  "
              f"median={sub['yaw_rmse'].median():.4f}  "
              f"cte mean={cte.mean():.3f}  median={cte.median():.3f}")
    # Total aggregate (weighted equally per segment)
    cte = df["cte_rmse"].dropna()
    print(f"\n[ALL] n={len(df)}  yaw_rmse mean={df['yaw_rmse'].mean():.4f}  "
          f"median={df['yaw_rmse'].median():.4f}  "
          f"cte mean={cte.mean():.3f}  median={cte.median():.3f}")
    df.to_csv("/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-10/eval_v0_results.csv", index=False)


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(limit=lim)
