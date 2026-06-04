"""Fit per-platform coefficients (g, L_eff, K_us, tau, delta0) by minimising
pooled yaw RMSE on each platform's segments using the V1 model shape.

Uses train/dev split (route-grouped) to detect overfit. Holds out ~20% of routes.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-02")


def _per_segment_delta0(sim_df, fallback=0.0, yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def model_yaw(sim_df, p):
    use_pseg = p["use_per_segment_delta0"]
    if use_pseg:
        delta0 = _per_segment_delta0(sim_df, fallback=p["delta0"])
    else:
        delta0 = p["delta0"]
    delta = (sim_df["delta_road_rad"].to_numpy() - delta0) * p["g"]
    v = sim_df["v_mps"].to_numpy()
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (p["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
    return yr


def load_segments(platform):
    paths = sorted((ROOT / "data" / "sim" / "segments" / platform).glob("**/sim.csv"))
    segs = []
    for p in paths:
        try:
            df = pd.read_csv(p)
            if "yaw_rate_meas_rads" not in df.columns:
                continue
            # route id = parent.parent
            route = p.parents[1].name
            segs.append((route, str(p), df))
        except Exception:
            continue
    return segs


def split_by_route(segs, dev_frac=0.2, seed=42):
    rng = np.random.default_rng(seed)
    routes = sorted({r for r, _, _ in segs})
    rng.shuffle(routes)
    n_dev = max(1, int(len(routes) * dev_frac))
    dev_routes = set(routes[:n_dev])
    train = [s for s in segs if s[0] not in dev_routes]
    dev = [s for s in segs if s[0] in dev_routes]
    return train, dev


def pooled_yaw_rmse(segs, params, v_thresh=2.0):
    sum_sq = 0.0
    n = 0
    for _, _, df in segs:
        v = df["v_mps"].to_numpy()
        mask = v > v_thresh
        if not mask.any():
            continue
        yr_pred = model_yaw(df, params)
        yr_truth = df["yaw_rate_meas_rads"].to_numpy()
        r = (yr_pred - yr_truth)[mask]
        sum_sq += float(np.sum(r * r))
        n += int(mask.sum())
    return float(np.sqrt(sum_sq / n)) if n > 0 else float("inf")


PLATFORMS = {
    "FORD_F_150_LIGHTNING_MK1": {
        "x0": [0.863, 3.26, 0.00350, 0.060, 0.00133],
        "use_per_segment_delta0": False,
        "bounds": [(0.6, 1.2), (2.0, 4.5), (0.0, 0.02), (0.01, 0.25), (-0.02, 0.02)],
    },
    "FORD_MUSTANG_MACH_E_MK1": {
        "x0": [0.891, 2.22, 0.00150, 0.069, -0.0001],
        "use_per_segment_delta0": True,
        "bounds": [(0.6, 1.2), (1.5, 4.0), (0.0, 0.02), (0.01, 0.25), (-0.02, 0.02)],
    },
    "HYUNDAI_IONIQ_5": {
        "x0": [0.938, 2.887, 0.00289, 0.062, 0.0],
        "use_per_segment_delta0": True,
        "bounds": [(0.6, 1.2), (1.5, 4.0), (0.0, 0.02), (0.01, 0.25), (-0.02, 0.02)],
    },
}


def fit_platform(platform, spec):
    print(f"\n== fitting {platform} ==")
    segs = load_segments(platform)
    print(f"  loaded {len(segs)} segments")
    train, dev = split_by_route(segs)
    print(f"  train={len(train)}, dev={len(dev)}")

    def to_params(x):
        return {
            "g": x[0],
            "L_eff": x[1],
            "K_us": x[2],
            "tau": x[3],
            "delta0": x[4],
            "use_per_segment_delta0": spec["use_per_segment_delta0"],
        }

    def obj(x):
        return pooled_yaw_rmse(train, to_params(x))

    x0 = np.array(spec["x0"], dtype=float)
    print(f"  x0 train_rmse = {obj(x0):.6f}")
    res = minimize(
        obj, x0, method="L-BFGS-B", bounds=spec["bounds"],
        options={"maxiter": 60, "ftol": 1e-9, "gtol": 1e-7},
    )
    print(f"  res.success={res.success}, nit={res.nit}, fun={res.fun:.6f}")
    print(f"  x_fit = {res.x.tolist()}")
    p_fit = to_params(res.x)
    train_rmse = pooled_yaw_rmse(train, p_fit)
    dev_rmse = pooled_yaw_rmse(dev, p_fit) if dev else float("nan")
    print(f"  train_rmse={train_rmse:.6f}, dev_rmse={dev_rmse:.6f}")
    return {
        "platform": platform,
        "g": float(res.x[0]), "L_eff": float(res.x[1]),
        "K_us": float(res.x[2]), "tau": float(res.x[3]),
        "delta0": float(res.x[4]),
        "use_per_segment_delta0": spec["use_per_segment_delta0"],
        "train_rmse": train_rmse, "dev_rmse": dev_rmse,
    }


if __name__ == "__main__":
    import json
    out = {}
    for plat, spec in PLATFORMS.items():
        out[plat] = fit_platform(plat, spec)
    with open(ROOT / "out" / "fitted_coeffs.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nwrote fitted_coeffs.json")
    print(json.dumps(out, indent=2))
