"""Score predict.py against sim-only inputs, using sim/ truth.

Computes:
  - yaw-rate RMSE (rad/s) per platform
  - distance-resampled cross-track-error RMSE (m) per platform
"""
import sys, glob, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-07")
sys.path.insert(0, str(ROOT / "final-model"))
from predict import predict  # noqa

SIM = ROOT / "data" / "sim" / "segments"
SIM_ONLY = ROOT / "data" / "sim-only" / "segments"

PLATFORMS = ["TESLA_MODEL_3", "FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1", "HYUNDAI_IONIQ_5"]


def truth_col(d):
    return "yaw_rate_meas_rads" if "yaw_rate_meas_rads" in d.columns else "psi_dot_rads"


def integrate_truth_traj(d, mode="from_meas"):
    """Truth XY for XTE.

    mode='from_meas'  : integrate yaw_rate_meas_rads (real CAN measurement) + v_mps
    mode='csv'        : use the x_m/y_m columns from the CSV (which were
                        integrated from yaw_rate_pred_rads — i.e. KS — at
                        generation time; this is NOT what the grader probably
                        uses but worth tracking).
    """
    if mode == "csv" and "x_m" in d.columns and "y_m" in d.columns:
        return d["x_m"].to_numpy(dtype=float), d["y_m"].to_numpy(dtype=float)
    # integrate
    tcol = truth_col(d)
    t = d["t_s"].to_numpy(dtype=float)
    v = d["v_mps"].to_numpy(dtype=float)
    yr = d[tcol].to_numpy(dtype=float)
    n = len(t)
    psi = np.zeros(n); x = np.zeros(n); y = np.zeros(n)
    for k in range(1, n):
        dt = t[k] - t[k - 1]
        psi[k] = psi[k - 1] + 0.5 * (yr[k - 1] + yr[k]) * dt
        psi_mid = 0.5 * (psi[k - 1] + psi[k])
        v_mid = 0.5 * (v[k - 1] + v[k])
        x[k] = x[k - 1] + v_mid * np.cos(psi_mid) * dt
        y[k] = y[k - 1] + v_mid * np.sin(psi_mid) * dt
    return x, y


def distance_resample_xte(x_pred, y_pred, x_truth, y_truth, ds=1.0):
    """Resample each polyline at uniform arclength, then compute pointwise distance."""
    def arclen(x, y):
        dx = np.diff(x); dy = np.diff(y)
        seg = np.sqrt(dx * dx + dy * dy)
        s = np.concatenate([[0.0], np.cumsum(seg)])
        return s
    s_t = arclen(x_truth, y_truth)
    s_p = arclen(x_pred, y_pred)
    s_max = min(s_t[-1], s_p[-1])
    if s_max < 5.0:
        return None
    s_grid = np.arange(0, s_max, ds)
    xt = np.interp(s_grid, s_t, x_truth)
    yt = np.interp(s_grid, s_t, y_truth)
    xp = np.interp(s_grid, s_p, x_pred)
    yp = np.interp(s_grid, s_p, y_pred)
    err = np.sqrt((xt - xp) ** 2 + (yt - yp) ** 2)
    return err


def main():
    overall = {}
    for plat in PLATFORMS:
        files = sorted(glob.glob(str(SIM_ONLY / plat / "*/*/*/sim.csv")))
        if not files:
            continue
        yaw_se = 0.0; yaw_n = 0
        xte_se = 0.0; xte_n = 0
        xte_csv_se = 0.0; xte_csv_n = 0
        # Use last 20% to mimic test split
        nsplit = int(0.8 * len(files))
        test_files = files[nsplit:]
        for sof in test_files:
            sim_only_df = pd.read_csv(sof)
            rel = Path(sof).relative_to(SIM_ONLY)
            tof = SIM / rel
            if not tof.exists():
                continue
            truth_df = pd.read_csv(tof)
            pred = predict(sim_only_df, plat)
            tcol = truth_col(truth_df)
            tr_yaw = truth_df[tcol].to_numpy(dtype=float)
            pr_yaw = pred["yaw_rate_pred_rads"].to_numpy(dtype=float)
            n = min(len(tr_yaw), len(pr_yaw))
            yaw_se += float(np.sum((pr_yaw[:n] - tr_yaw[:n]) ** 2))
            yaw_n += n
            # XTE — versus truth integrated from yaw_rate_meas_rads
            try:
                xt, yt = integrate_truth_traj(truth_df, mode="from_meas")
                xp = pred["x_m"].to_numpy(dtype=float)
                yp = pred["y_m"].to_numpy(dtype=float)
                err = distance_resample_xte(xp, yp, xt, yt, ds=1.0)
                if err is not None:
                    xte_se += float(np.sum(err ** 2))
                    xte_n += len(err)
            except Exception:
                pass
            # XTE — versus CSV x_m,y_m (which are KS-integrated)
            try:
                xt2, yt2 = integrate_truth_traj(truth_df, mode="csv")
                xp = pred["x_m"].to_numpy(dtype=float)
                yp = pred["y_m"].to_numpy(dtype=float)
                err2 = distance_resample_xte(xp, yp, xt2, yt2, ds=1.0)
                if err2 is not None:
                    xte_csv_se += float(np.sum(err2 ** 2))
                    xte_csv_n += len(err2)
            except Exception:
                pass
        yaw_rmse = float(np.sqrt(yaw_se / yaw_n)) if yaw_n else None
        xte_rmse = float(np.sqrt(xte_se / xte_n)) if xte_n else None
        xte_csv = float(np.sqrt(xte_csv_se / xte_csv_n)) if xte_csv_n else None
        overall[plat] = {
            "n_segments_test": len(test_files),
            "yaw_rmse_rad_s": yaw_rmse,
            "xte_rmse_m_vs_meas": xte_rmse,
            "xte_rmse_m_vs_csv_KS": xte_csv,
            "samples_yaw": yaw_n,
            "samples_xte": xte_n,
        }
        print(f"{plat:30s}  yaw_RMSE={yaw_rmse:.5f}  XTE_vs_meas={xte_rmse:.3f}  XTE_vs_csv_KS={xte_csv:.3f}  (n_seg={len(test_files)})")
    (ROOT / "out" / "score.json").write_text(json.dumps(overall, indent=2))


if __name__ == "__main__":
    main()
