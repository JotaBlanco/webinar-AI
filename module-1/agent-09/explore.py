"""Explore Ford sim CSVs and fit a per-platform linear bicycle (understeer) model.

Fits:  psi_dot_pred = (v * (delta - delta0)) / (L + K * v^2)

via least-squares over the residual structure on the train set.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
SIM = DATA / "sim" / "segments"
CODE = HERE / "code"
sys.path.insert(0, str(CODE))
from parameters import PARAM_BY_PLATFORM  # noqa: E402


PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1"]


def load_segments(platform: str):
    man = json.loads((SIM / platform / "manifest.json").read_text())
    rows = []
    for seg in man["segments"]:
        path = DATA / "sim" / seg["csv_path"]
        if path.exists():
            rows.append(path)
    return rows


def load_concat(platform: str, paths):
    frames = []
    for p in paths:
        df = pd.read_csv(p)
        frames.append(df)
    return frames


def fit_understeer(frames, L):
    """Fit psi_dot = (v*(delta - delta0)) / (L + K * v^2).

    Linearise: let y = psi_dot, x_d = v*delta, x_v = psi_dot*v^2, x_const = v.
    psi_dot * (L + K v^2) = v * (delta - delta0)
    y*L + y*K*v^2 = v*delta - v*delta0
    -> v*delta = y*L + y*K*v^2 + v*delta0
    -> rearranging:  y*K*v^2 + v*delta0 = v*delta - y*L
       Let beta=[K, delta0]; design matrix A = [y*v^2, v]; target b = v*delta - y*L
    Use only steady, mid-speed samples to be robust.
    """
    Xrows = []
    brows = []
    for df in frames:
        v = df["v_mps"].to_numpy()
        delta = df["delta_road_rad"].to_numpy()
        y = df["yaw_rate_meas_rads"].to_numpy()
        # mask: minimum speed, no NaNs
        m = (v > 5.0) & np.isfinite(y) & np.isfinite(delta)
        Xrows.append(np.column_stack([y[m] * v[m] ** 2, v[m]]))
        brows.append(v[m] * delta[m] - y[m] * L)
    A = np.vstack(Xrows)
    b = np.concatenate(brows)
    # Solve least squares  A @ [K, delta0] = b
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    K, delta0 = float(sol[0]), float(sol[1])
    return K, delta0


def predict_yaw(df, L, K, delta0):
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    return (v * (delta - delta0)) / (L + K * v ** 2)


def rmse(a, b):
    return float(np.sqrt(np.mean((a - b) ** 2)))


def integrate_xy(t, v, psi_dot):
    """Integrate (x,y,psi) trajectory from yaw rate and speed."""
    psi = np.cumsum(psi_dot[:-1] * np.diff(t))
    psi = np.concatenate([[0.0], psi])
    # use midpoint heading for trapezoidal step
    x = np.zeros_like(t)
    y = np.zeros_like(t)
    for k in range(len(t) - 1):
        dt = t[k + 1] - t[k]
        # midpoint heading
        psi_m = 0.5 * (psi[k] + psi[k + 1])
        v_m = 0.5 * (v[k] + v[k + 1])
        x[k + 1] = x[k] + v_m * np.cos(psi_m) * dt
        y[k + 1] = y[k] + v_m * np.sin(psi_m) * dt
    return x, y, psi


def cte_rmse_distance_resampled(t, v, psi_dot_true, psi_dot_pred, ds=1.0):
    """Distance-resampled cross-track-error RMSE.

    Builds two trajectories from the same v(t), one with true yaw, one with pred,
    then resamples both onto a uniform arc-length grid based on the *true*
    trajectory, and computes perpendicular distance from pred to true.

    Simpler proxy: at each true arc length s, find closest point on pred path.
    Even simpler: same time index distance, but resampled by arc length of TRUE.
    """
    xt, yt, _ = integrate_xy(t, v, psi_dot_true)
    xp, yp, _ = integrate_xy(t, v, psi_dot_pred)
    # arc length along truth
    ds_true = np.sqrt(np.diff(xt) ** 2 + np.diff(yt) ** 2)
    s_true = np.concatenate([[0.0], np.cumsum(ds_true)])
    if s_true[-1] < 2 * ds:
        return float("nan")
    s_grid = np.arange(0, s_true[-1], ds)
    # Resample both at common time indices -- simple point-distance proxy
    # We index pred by same time index as truth (since v(t) is shared).
    # Cross-track at every sample = euclidean distance between same-time points,
    # then resampled by truth arc-length.
    dxy = np.sqrt((xt - xp) ** 2 + (yt - yp) ** 2)
    dxy_resamp = np.interp(s_grid, s_true, dxy)
    return float(np.sqrt(np.mean(dxy_resamp ** 2)))


def eval_platform(platform: str, train_frac: float = 0.7):
    p = PARAM_BY_PLATFORM[platform]
    paths = load_segments(platform)
    rng = np.random.default_rng(42)
    idx = np.arange(len(paths))
    rng.shuffle(idx)
    n_train = int(train_frac * len(idx))
    train_idx, eval_idx = idx[:n_train], idx[n_train:]

    train_frames = [pd.read_csv(paths[i]) for i in train_idx]
    print(f"[{platform}] N={len(paths)}  train={len(train_frames)}  eval={len(eval_idx)}")

    K, delta0 = fit_understeer(train_frames, p.L)
    print(f"   fitted: K = {K:.5f}  delta0 = {delta0:.5f}  (L = {p.L})")

    # Evaluate on eval pool
    v0_yaw_rmses = []
    v1_yaw_rmses = []
    v0_cte = []
    v1_cte = []
    for i in eval_idx:
        df = pd.read_csv(paths[i])
        v = df["v_mps"].to_numpy()
        t = df["t_s"].to_numpy()
        y_meas = df["yaw_rate_meas_rads"].to_numpy()
        y_v0 = df["yaw_rate_pred_rads"].to_numpy()
        y_v1 = predict_yaw(df, p.L, K, delta0)
        m = np.isfinite(y_meas) & np.isfinite(y_v1)
        v0_yaw_rmses.append(rmse(y_meas[m], y_v0[m]))
        v1_yaw_rmses.append(rmse(y_meas[m], y_v1[m]))
        v0_cte.append(cte_rmse_distance_resampled(t, v, y_meas, y_v0))
        v1_cte.append(cte_rmse_distance_resampled(t, v, y_meas, y_v1))
    print(f"   V0 yaw RMSE: mean={np.nanmean(v0_yaw_rmses):.5f}  median={np.nanmedian(v0_yaw_rmses):.5f}")
    print(f"   V1 yaw RMSE: mean={np.nanmean(v1_yaw_rmses):.5f}  median={np.nanmedian(v1_yaw_rmses):.5f}")
    print(f"   V0 CTE RMSE: mean={np.nanmean(v0_cte):.3f} m  median={np.nanmedian(v0_cte):.3f}")
    print(f"   V1 CTE RMSE: mean={np.nanmean(v1_cte):.3f} m  median={np.nanmedian(v1_cte):.3f}")
    return {"platform": platform, "K": K, "delta0": delta0,
            "v0_yaw_rmse_mean": float(np.nanmean(v0_yaw_rmses)),
            "v1_yaw_rmse_mean": float(np.nanmean(v1_yaw_rmses)),
            "v0_cte_mean": float(np.nanmean(v0_cte)),
            "v1_cte_mean": float(np.nanmean(v1_cte))}


if __name__ == "__main__":
    results = {}
    for plat in PLATFORMS:
        results[plat] = eval_platform(plat)
    out = HERE / "exploration_results.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\nSaved: {out}")
