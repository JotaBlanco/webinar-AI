"""Per-platform fit of (g, L_eff, K_us, tau, delta0/fallback) against yaw+CTE.

Train on data/sim/ (has truth) per platform. Optimise yaw RMSE primarily, with
a small CTE-bias penalty (signed yaw residual mean) to keep CTE in check.

Per-segment delta0 platforms: Mach-E + IONIQ-5. Lightning uses global delta0.
"""
import sys, os, json, math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-06")
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "out"))

from traj_metrics import cte_diagnostics_segment


def _per_segment_delta0(yr_v0, v, delta_road, fallback=0.0,
                        yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(np.median(delta_road[mask]))


def yaw_predict(sim_df, p, use_per_segment_delta0, delta0_fallback):
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    delta_r = sim_df["delta_road_rad"].to_numpy()
    if use_per_segment_delta0:
        delta0 = _per_segment_delta0(yr_v0, v, delta_r, fallback=delta0_fallback)
    else:
        delta0 = delta0_fallback
    delta = (delta_r - delta0) * p["g"]
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (p["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
    return yr


def load_platform_segments(platform, max_segments=None):
    root = ROOT / "data" / "sim" / "segments" / platform
    paths = sorted(p for p in root.glob("*/**/sim.csv") if p.is_file())
    if max_segments is not None:
        # Stride-subsample for train/dev split.
        paths = paths[::max(1, len(paths)//max_segments)][:max_segments]
    out = []
    for p in paths:
        try:
            df = pd.read_csv(p)
            if "yaw_rate_meas_rads" not in df.columns:
                continue
            out.append(df)
        except Exception:
            continue
    return out


def objective_factory(segs, use_per_segment_delta0, cte_weight=300.0):
    """Returns (yaw_rmse, cte_rmse, combined_loss)."""
    def loss(theta):
        if use_per_segment_delta0:
            g, L_eff, K_us, tau, delta0_fallback = theta
        else:
            g, L_eff, K_us, tau, delta0_fallback = theta
        # bounds clip
        if not (0.5 < g < 1.2 and 1.5 < L_eff < 5.0 and 0 <= K_us < 0.02
                and 0.005 < tau < 0.5 and -0.05 < delta0_fallback < 0.05):
            return 1e6
        p = {"g": g, "L_eff": L_eff, "K_us": K_us, "tau": tau}
        sum_sq = 0.0
        sum_signed = 0.0
        n = 0
        cte_sum_sq = 0.0
        cte_n = 0
        for df in segs:
            yr = yaw_predict(df, p, use_per_segment_delta0, delta0_fallback)
            v = df["v_mps"].to_numpy()
            yr_truth = df["yaw_rate_meas_rads"].to_numpy()
            mask = v > 2.0
            if not mask.any():
                continue
            r = yr[mask] - yr_truth[mask]
            sum_sq += float(np.sum(r*r))
            sum_signed += float(np.sum(r))
            n += int(mask.sum())
            # CTE: use traj_metrics
            t = df["t_s"].to_numpy()
            try:
                cte = cte_diagnostics_segment(t, v, yr_truth, yr,
                                              grid_step_m=1.0, min_distance_m=20.0)
                if cte["n_bins"] > 0:
                    cte_sum_sq += cte["sum_sq_m2"]
                    cte_n += cte["n_bins"]
            except Exception:
                pass
        if n == 0:
            return 1e6
        yaw_rmse = math.sqrt(sum_sq / n)
        cte_rmse = math.sqrt(cte_sum_sq / cte_n) if cte_n > 0 else 0.0
        # combined loss: yaw RMSE + small CTE
        return yaw_rmse + cte_weight * (cte_rmse / 1000.0)
    return loss


def fit_platform(platform, use_per_segment_delta0, x0, max_segments=60):
    print(f"\n=== Fitting {platform} (per_segment_delta0={use_per_segment_delta0}) ===")
    segs = load_platform_segments(platform, max_segments=max_segments)
    print(f"  loaded {len(segs)} training segments")
    if not segs:
        return None
    loss = objective_factory(segs, use_per_segment_delta0)
    print(f"  loss at x0={x0}: {loss(x0):.6f}")
    res = minimize(loss, x0, method="Nelder-Mead",
                   options={"xatol": 1e-5, "fatol": 1e-6, "maxiter": 400, "disp": True})
    print(f"  fit result: {res.x}")
    print(f"  final loss: {res.fun:.6f}")
    g, L_eff, K_us, tau, delta0 = res.x
    return {
        "g": float(g), "L_eff": float(L_eff), "K_us": float(K_us),
        "tau": float(tau),
        "use_per_segment_delta0": bool(use_per_segment_delta0),
        ("delta0_fallback" if use_per_segment_delta0 else "delta0"): float(delta0),
    }


if __name__ == "__main__":
    fits = {}

    # Lightning — global delta0
    x0 = [0.863, 3.26, 0.00350, 0.060, 0.00133]
    r = fit_platform("FORD_F_150_LIGHTNING_MK1", False, x0, max_segments=80)
    if r: fits["FORD_F_150_LIGHTNING_MK1"] = r

    # Mach-E — per-segment delta0
    x0 = [0.891, 2.22, 0.00150, 0.069, -0.0001]
    r = fit_platform("FORD_MUSTANG_MACH_E_MK1", True, x0, max_segments=80)
    if r: fits["FORD_MUSTANG_MACH_E_MK1"] = r

    # IONIQ-5 — per-segment delta0
    x0 = [0.938, 2.887, 0.00289, 0.062, 0.0]
    r = fit_platform("HYUNDAI_IONIQ_5", True, x0, max_segments=80)
    if r: fits["HYUNDAI_IONIQ_5"] = r

    out = ROOT / "out" / "coeffs_fitted.json"
    with open(out, "w") as f:
        json.dump(fits, f, indent=2)
    print(f"\nSaved fitted coeffs to {out}")
    print(json.dumps(fits, indent=2))
