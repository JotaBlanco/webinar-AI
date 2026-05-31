"""Local score: yaw RMSE + distance-resampled cross-track error.

Trains the contract: load sim-only/segments/ for inputs (no truth column),
load matching sim/segments/ for truth, run predict() over sim-only.
"""
import glob, os, sys, json
import numpy as np
import pandas as pd

sys.path.insert(0, "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-06/final-model")
from predict import predict, _integrate_xy

SIM_ONLY = "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-06/data/sim-only/segments"
SIM = "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-06/data/sim/segments"

PLATFORMS = ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1", "HYUNDAI_IONIQ_5", "TESLA_MODEL_3"]

def truth_xy(t, v, yaw_rate):
    return _integrate_xy(t, v, yaw_rate)

def distance_resample_xte(t, v, yaw_pred, yaw_truth, ds=1.0):
    """Compute cross-track error after distance-resampling.

    Cross-track for two trajectories from same start: take pred (x_p,y_p),
    truth (x_t,y_t), resample by arclength of truth at uniform ds, compute
    per-sample euclidean displacement → RMSE.
    """
    x_p, y_p = _integrate_xy(t, v, yaw_pred)
    x_t, y_t = _integrate_xy(t, v, yaw_truth)
    # arclength of truth
    dx = np.diff(x_t); dy = np.diff(y_t)
    seg = np.sqrt(dx*dx + dy*dy)
    s_t = np.concatenate([[0.0], np.cumsum(seg)])
    if s_t[-1] < ds * 2:
        # too short to resample
        d = np.sqrt((x_p - x_t)**2 + (y_p - y_t)**2)
        return float(np.sqrt(np.mean(d**2))), float(s_t[-1])
    s_u = np.arange(0, s_t[-1], ds)
    # interpolate both trajectories onto s_t (truth's natural arclength)
    xt_u = np.interp(s_u, s_t, x_t)
    yt_u = np.interp(s_u, s_t, y_t)
    xp_u = np.interp(s_u, s_t, x_p)
    yp_u = np.interp(s_u, s_t, y_p)
    d = np.sqrt((xp_u - xt_u)**2 + (yp_u - yt_u)**2)
    return float(np.sqrt(np.mean(d**2))), float(s_t[-1])

results = {}
for p in PLATFORMS:
    so_paths = sorted(glob.glob(f"{SIM_ONLY}/{p}/*/*/*/sim.csv"))
    # take a sample (300 segments) for speed
    rng = np.random.default_rng(7)
    if len(so_paths) > 300:
        idx = rng.choice(len(so_paths), 300, replace=False)
        so_paths = [so_paths[i] for i in idx]

    yaw_rmses_v0 = []
    yaw_rmses_v1 = []
    xte_rmses_v1 = []
    xte_rmses_v0 = []
    n_with_truth = 0

    for so_path in so_paths:
        rel = os.path.relpath(so_path, SIM_ONLY)
        sim_path = os.path.join(SIM, rel)
        d_so = pd.read_csv(so_path)
        try:
            d_sim = pd.read_csv(sim_path)
        except Exception:
            continue
        if "yaw_rate_meas_rads" not in d_sim.columns:
            continue
        if len(d_so) != len(d_sim):
            continue
        n_with_truth += 1

        out = predict(d_so, p)
        yaw_v1 = out["yaw_rate_pred_rads"].to_numpy()
        yaw_v0 = d_so["yaw_rate_pred_rads"].to_numpy()
        yaw_t  = d_sim["yaw_rate_meas_rads"].to_numpy()

        yaw_rmses_v0.append(np.sqrt(np.mean((yaw_v0 - yaw_t)**2)))
        yaw_rmses_v1.append(np.sqrt(np.mean((yaw_v1 - yaw_t)**2)))

        t = d_so["t_s"].to_numpy()
        v = d_so["v_mps"].to_numpy()
        xte_v1, _ = distance_resample_xte(t, v, yaw_v1, yaw_t, ds=1.0)
        xte_v0, _ = distance_resample_xte(t, v, yaw_v0, yaw_t, ds=1.0)
        xte_rmses_v1.append(xte_v1)
        xte_rmses_v0.append(xte_v0)

    if n_with_truth == 0:
        print(f"\n{p}: no truth available → can't local-score (Tesla)")
        results[p] = dict(n=0, note="no truth in sim/")
        continue

    def agg(xs):
        return float(np.sqrt(np.mean(np.array(xs)**2)))
    res = dict(
        n=n_with_truth,
        yaw_rmse_v0=agg(yaw_rmses_v0),
        yaw_rmse_v1=agg(yaw_rmses_v1),
        xte_rmse_v0=agg(xte_rmses_v0),
        xte_rmse_v1=agg(xte_rmses_v1),
    )
    results[p] = res
    print(f"\n=== {p}  (n={n_with_truth} segments) ===")
    print(f"  yaw RMSE  V0={res['yaw_rmse_v0']:.5f}   V1={res['yaw_rmse_v1']:.5f}")
    print(f"  XTE RMSE  V0={res['xte_rmse_v0']:.3f} m V1={res['xte_rmse_v1']:.3f} m")

with open("/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-06/out/score.json","w") as f:
    json.dump(results, f, indent=2)
print("\nwrote out/score.json")
