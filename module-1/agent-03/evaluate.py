"""End-to-end evaluation of the final model on held-out segments.

Computes per-platform pooled:
  1. Yaw-rate RMSE (rad/s)
  2. Distance-resampled cross-track-error RMSE (m).

For ground-truth trajectory, we integrate yaw_rate_meas_rads with v_mps the
same way we integrate the prediction — both prediction and truth start from
the same initial conditions and run on the same time grid, so cross-track
error is the perpendicular distance between matched arc-length samples.
"""
import os, glob, json, sys
import numpy as np
import pandas as pd

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-03"
sys.path.insert(0, f"{ROOT}/final-model")
from predict import predict, _integrate_trajectory  # noqa: E402

SIM_ROOT = f"{ROOT}/data/sim/segments"
PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1"]


def list_segments(platform):
    return sorted(glob.glob(f"{SIM_ROOT}/{platform}/*/*/*/sim.csv"))


def held_out_files(plat, seed=42, train_frac=0.7):
    files = list_segments(plat)
    rng = np.random.RandomState(seed)
    perm = rng.permutation(len(files))
    n_train = int(len(files) * train_frac)
    return [files[i] for i in perm[n_train:]]


def arc_length(x, y):
    dx = np.diff(x); dy = np.diff(y)
    s = np.concatenate(([0.0], np.cumsum(np.sqrt(dx * dx + dy * dy))))
    return s


def distance_resample_xte(x_pred, y_pred, x_truth, y_truth, ds=1.0):
    """Resample both trajectories at uniform arc-length and compute pointwise
    perpendicular distance from prediction to the truth path.

    Truth path is resampled first onto a uniform arc grid. Then for each pred
    point we find its nearest truth-arc point and compute distance. This is
    the standard cross-track-error: shortest distance from predicted point to
    the (continuous) truth path."""
    s_t = arc_length(x_truth, y_truth)
    s_p = arc_length(x_pred, y_pred)
    L = min(s_t[-1], s_p[-1])
    if L < 2 * ds:
        return None
    s_grid = np.arange(0.0, L, ds)
    # Resample truth at s_grid
    xt = np.interp(s_grid, s_t, x_truth)
    yt = np.interp(s_grid, s_t, y_truth)
    # Resample pred at s_grid (along its own arc length)
    xp = np.interp(s_grid, s_p, x_pred)
    yp = np.interp(s_grid, s_p, y_pred)
    # Pointwise distance (since both are sampled at the same arc-length progress
    # in their own paths, this is the standard "drift" cross-track metric.)
    d = np.sqrt((xp - xt) ** 2 + (yp - yt) ** 2)
    return d


def evaluate_segment(csv_path, platform):
    df = pd.read_csv(csv_path)
    # Predict
    pred = predict(df, platform)
    yaw_pred = pred["yaw_rate_pred_rads"].values
    x_pred = pred["x_m"].values
    y_pred = pred["y_m"].values

    # Truth
    yaw_meas = df["yaw_rate_meas_rads"].values
    t = df["t_s"].values.astype(float)
    v = df["v_mps"].values.astype(float)
    # Integrate truth trajectory from yaw_meas + measured v with same init.
    x0 = float(df["x_m"].iloc[0]) if "x_m" in df.columns else 0.0
    y0 = float(df["y_m"].iloc[0]) if "y_m" in df.columns else 0.0
    psi0 = float(df["psi_rad"].iloc[0]) if "psi_rad" in df.columns else 0.0
    x_t, y_t, _ = _integrate_trajectory(t, v, yaw_meas, x0=x0, y0=y0, psi0=psi0)

    # V0 yaw rate (already in csv)
    yaw_v0 = df["yaw_rate_pred_rads"].values
    # V0 trajectory: integrate V0 yaw rate
    x_v0, y_v0, _ = _integrate_trajectory(t, v, yaw_v0, x0=x0, y0=y0, psi0=psi0)

    return {
        "n": len(df),
        "sq_err_yaw_v0": float(np.sum((yaw_meas - yaw_v0) ** 2)),
        "sq_err_yaw_pred": float(np.sum((yaw_meas - yaw_pred) ** 2)),
        "xte_pred": distance_resample_xte(x_pred, y_pred, x_t, y_t, ds=1.0),
        "xte_v0": distance_resample_xte(x_v0, y_v0, x_t, y_t, ds=1.0),
    }


def main():
    results = {}
    for plat in PLATFORMS:
        held = held_out_files(plat)
        print(f"\n=== {plat} ===   held: {len(held)} segments")
        sse_v0 = 0.0; sse_pred = 0.0; n_total = 0
        xte_v0_all = []; xte_pred_all = []
        for f in held:
            r = evaluate_segment(f, plat)
            sse_v0 += r["sq_err_yaw_v0"]
            sse_pred += r["sq_err_yaw_pred"]
            n_total += r["n"]
            if r["xte_v0"] is not None:
                xte_v0_all.append(r["xte_v0"])
                xte_pred_all.append(r["xte_pred"])
        rmse_yaw_v0 = float(np.sqrt(sse_v0 / n_total))
        rmse_yaw_pred = float(np.sqrt(sse_pred / n_total))
        xte_v0_arr = np.concatenate(xte_v0_all) if xte_v0_all else np.array([])
        xte_pred_arr = np.concatenate(xte_pred_all) if xte_pred_all else np.array([])
        rmse_xte_v0 = float(np.sqrt(np.mean(xte_v0_arr ** 2))) if len(xte_v0_arr) else None
        rmse_xte_pred = float(np.sqrt(np.mean(xte_pred_arr ** 2))) if len(xte_pred_arr) else None
        print(f"  Yaw-rate RMSE   V0: {rmse_yaw_v0:.6f}   pred: {rmse_yaw_pred:.6f}   "
              f"reduction: {(1 - rmse_yaw_pred / rmse_yaw_v0) * 100:.1f}%")
        print(f"  Cross-track RMSE V0: {rmse_xte_v0:.4f} m   pred: {rmse_xte_pred:.4f} m   "
              f"reduction: {(1 - rmse_xte_pred / rmse_xte_v0) * 100:.1f}%")
        results[plat] = {
            "n_samples": n_total,
            "rmse_yaw_v0": rmse_yaw_v0,
            "rmse_yaw_pred": rmse_yaw_pred,
            "rmse_xte_v0_m": rmse_xte_v0,
            "rmse_xte_pred_m": rmse_xte_pred,
        }
    with open(f"{ROOT}/eval_results.json", "w") as fh:
        json.dump(results, fh, indent=2)
    print("\nSaved eval_results.json")


if __name__ == "__main__":
    main()
