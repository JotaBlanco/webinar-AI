"""V2: per-platform refit of (g, L_eff, K_us, tau, delta0_fallback) for the three Ford/Hyundai platforms.

Strategy:
- Group segments by route -> route-grouped train/dev split (80/20).
- For each platform, run scipy.optimize.minimize on a yaw+CTE composite objective.
- Save fitted coeffs to coeffs.json.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-05")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "_shared"))

from score import score
from traj_metrics import cte_diagnostics_segment


def _per_segment_delta0(sim_df, fallback=0.0,
                        yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def predict_one(sim_df, params):
    g, L_eff, K_us, tau = params["g"], params["L_eff"], params["K_us"], params["tau"]
    if params.get("use_per_segment_delta0", False):
        delta0 = _per_segment_delta0(sim_df, fallback=params.get("delta0_fallback", 0.0))
    else:
        delta0 = params["delta0"]
    delta = (sim_df["delta_road_rad"].to_numpy() - delta0) * g
    v = sim_df["v_mps"].to_numpy()
    yr_ss = v * delta / (L_eff + K_us * v * v)
    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
    return yr


def load_segments(platform, max_segments=200, seed=7):
    seg_root = ROOT / "data" / "sim" / "segments" / platform
    paths = sorted(p for p in seg_root.glob("**/sim.csv") if p.is_file())
    if len(paths) > max_segments:
        rng = np.random.default_rng(seed)
        # Route-stratified subsample so dev split is still meaningful
        routes_map = {}
        for p in paths:
            r = p.resolve().parents[1].name
            routes_map.setdefault(r, []).append(p)
        routes = list(routes_map.keys())
        rng.shuffle(routes)
        sel = []
        for r in routes:
            sel.extend(routes_map[r])
            if len(sel) >= max_segments:
                break
        paths = sel[:max_segments]
    out = []
    for p in paths:
        df = pd.read_csv(p)
        route = p.resolve().parents[1].name
        out.append((route, str(p), df))
    return out


def route_split(segments, frac_dev=0.2, seed=42):
    routes = sorted({r for r, _, _ in segments})
    rng = np.random.default_rng(seed)
    rng.shuffle(routes)
    n_dev = max(1, int(len(routes) * frac_dev))
    dev_routes = set(routes[:n_dev])
    train, dev = [], []
    for r, p, df in segments:
        (dev if r in dev_routes else train).append((r, p, df))
    return train, dev


def pooled_metrics(segments, params):
    yaw_sum_sq = 0.0
    yaw_n = 0
    cte_sum_sq = 0.0
    cte_n = 0
    for _, _, df in segments:
        t = df["t_s"].to_numpy(float)
        v = df["v_mps"].to_numpy(float)
        if len(t) < 2 or np.any(np.diff(t) <= 0):
            continue
        # mimic score-model: provide allowlist subset
        sim_df_agent = df.copy()
        yr_pred = predict_one(sim_df_agent, params)
        yr_truth = df["yaw_rate_meas_rads"].to_numpy(float)
        mask_v = v > 2.0
        resid = yr_pred - yr_truth
        yaw_sum_sq += float(np.sum(resid[mask_v]**2))
        yaw_n += int(mask_v.sum())
        cte = cte_diagnostics_segment(t, v, yr_truth, yr_pred,
                                       grid_step_m=1.0, min_distance_m=20.0)
        cte_sum_sq += cte["sum_sq_m2"]
        cte_n += cte["n_bins"]
    yaw_rmse = math.sqrt(yaw_sum_sq / yaw_n) if yaw_n > 0 else float("nan")
    cte_rmse = math.sqrt(cte_sum_sq / cte_n) if cte_n > 0 else float("nan")
    return yaw_rmse, cte_rmse


def fit_platform(platform, init, use_psd0, delta0_key, bounds, train, dev):
    keys = ["g", "L_eff", "K_us", "tau", delta0_key]
    x0 = [init[k] for k in keys]
    bounds_arr = [bounds[k] for k in keys]

    def make_params(x):
        p = {keys[i]: float(x[i]) for i in range(len(keys))}
        p["use_per_segment_delta0"] = use_psd0
        if use_psd0:
            # x[-1] is delta0_fallback
            pass
        else:
            pass
        return p

    def obj(x):
        params = make_params(x)
        yaw, cte = pooled_metrics(train, params)
        # composite: normalised
        return (yaw / 0.01) ** 2 + (cte / 50.0) ** 2

    res = minimize(obj, x0, method="L-BFGS-B", bounds=bounds_arr,
                   options={"maxiter": 30, "ftol": 1e-5})
    best = make_params(res.x)
    train_yaw, train_cte = pooled_metrics(train, best)
    dev_yaw, dev_cte = pooled_metrics(dev, best)
    print(f"[{platform}] fit: {dict((k, round(v, 5) if isinstance(v, float) else v) for k, v in best.items())}")
    print(f"  train: yaw={train_yaw:.5f} cte={train_cte:.3f}  dev: yaw={dev_yaw:.5f} cte={dev_cte:.3f}")
    return best


def main():
    out = {}
    init_lightning = {"g": 0.863, "L_eff": 3.26, "K_us": 0.00350, "tau": 0.060, "delta0": 0.00133}
    init_machE     = {"g": 0.891, "L_eff": 2.22, "K_us": 0.00150, "tau": 0.069, "delta0_fallback": -0.0001}
    init_ioniq     = {"g": 0.938, "L_eff": 2.887, "K_us": 0.00289, "tau": 0.062, "delta0_fallback": 0.0}
    bounds_common = {"g": (0.6, 1.2), "L_eff": (1.8, 4.0), "K_us": (0.0, 0.02), "tau": (0.01, 0.25)}

    for platform, init, use_psd0, delta0_key in [
        ("FORD_F_150_LIGHTNING_MK1", init_lightning, False, "delta0"),
        ("FORD_MUSTANG_MACH_E_MK1",  init_machE,     True,  "delta0_fallback"),
        ("HYUNDAI_IONIQ_5",          init_ioniq,     True,  "delta0_fallback"),
    ]:
        print(f"\n==== Fitting {platform} ====")
        segs = load_segments(platform)
        train, dev = route_split(segs)
        print(f"  train segments: {len(train)}, dev segments: {len(dev)}")
        bounds = dict(bounds_common)
        bounds[delta0_key] = (-0.05, 0.05)
        best = fit_platform(platform, init, use_psd0, delta0_key, bounds, train, dev)
        out[platform] = best

    coeffs_path = ROOT / "out" / "coeffs.json"
    coeffs_path.write_text(json.dumps(out, indent=2))
    print(f"\nSaved coeffs to {coeffs_path}")


if __name__ == "__main__":
    main()
