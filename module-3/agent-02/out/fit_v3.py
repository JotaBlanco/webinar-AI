"""Fit with yaw_RMSE + lambda * |signed_mean_residual| penalty per platform.

The signed mean residual is the strongest predictor of CTE drift (CTE is the
double-integral of yaw-rate error; systematic bias dominates). Adding it as a
penalty steers the fit toward an unbiased solution at the cost of a tiny yaw
RMSE penalty.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-02")
sys.path.insert(0, str(ROOT / "out"))
from fit_v2 import load_segments, split_by_route, model_yaw  # noqa: E402


def pooled_yaw_metrics(segs, params, v_thresh=2.0):
    sum_sq = 0.0
    sum_signed = 0.0
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
        sum_signed += float(np.sum(r))
        n += int(mask.sum())
    rmse = float(np.sqrt(sum_sq / n)) if n > 0 else float("inf")
    bias = float(sum_signed / n) if n > 0 else float("inf")
    return rmse, bias


PLATFORMS = {
    "FORD_F_150_LIGHTNING_MK1": {
        "x0": [0.863, 3.26, 0.00350, 0.060, 0.00133],
        "use_per_segment_delta0": False,
        "bounds": [(0.6, 1.2), (2.0, 4.5), (0.0, 0.02), (0.01, 0.25), (-0.02, 0.02)],
        "bias_weight": 5.0,
    },
    "FORD_MUSTANG_MACH_E_MK1": {
        "x0": [0.891, 2.22, 0.00150, 0.069, -0.0001],
        "use_per_segment_delta0": True,
        "bounds": [(0.6, 1.2), (1.5, 4.0), (0.0, 0.02), (0.01, 0.25), (-0.02, 0.02)],
        "bias_weight": 5.0,
    },
    "HYUNDAI_IONIQ_5": {
        "x0": [0.938, 2.887, 0.00289, 0.062, 0.0],
        "use_per_segment_delta0": True,
        "bounds": [(0.6, 1.2), (1.5, 4.0), (0.0, 0.02), (0.01, 0.25), (-0.02, 0.02)],
        "bias_weight": 5.0,
    },
}


def fit_platform(platform, spec):
    print(f"\n== fitting {platform} ==")
    segs = load_segments(platform)
    train, dev = split_by_route(segs)
    print(f"  train={len(train)}, dev={len(dev)}")

    def to_params(x):
        return {"g": x[0], "L_eff": x[1], "K_us": x[2], "tau": x[3],
                "delta0": x[4],
                "use_per_segment_delta0": spec["use_per_segment_delta0"]}

    bw = spec["bias_weight"]

    def obj(x):
        p = to_params(x)
        rmse, bias = pooled_yaw_metrics(train, p)
        return rmse * rmse + bw * bias * bias

    x0 = np.array(spec["x0"], dtype=float)
    rmse0, b0 = pooled_yaw_metrics(train, to_params(x0))
    print(f"  x0 rmse={rmse0:.6f}, bias={b0:+.6f}")
    res = minimize(obj, x0, method="L-BFGS-B", bounds=spec["bounds"],
                   options={"maxiter": 80, "ftol": 1e-10, "gtol": 1e-8})
    p_fit = to_params(res.x)
    train_rmse, train_bias = pooled_yaw_metrics(train, p_fit)
    dev_rmse, dev_bias = pooled_yaw_metrics(dev, p_fit) if dev else (float("nan"), float("nan"))
    print(f"  fit: rmse={train_rmse:.6f}, bias={train_bias:+.6f}")
    print(f"  dev: rmse={dev_rmse:.6f}, bias={dev_bias:+.6f}")
    print(f"  x_fit = {res.x.tolist()}")
    return {
        "platform": platform,
        "g": float(res.x[0]), "L_eff": float(res.x[1]),
        "K_us": float(res.x[2]), "tau": float(res.x[3]),
        "delta0": float(res.x[4]),
        "use_per_segment_delta0": spec["use_per_segment_delta0"],
        "train_rmse": train_rmse, "train_bias": train_bias,
        "dev_rmse": dev_rmse, "dev_bias": dev_bias,
    }


if __name__ == "__main__":
    import json
    out = {}
    for plat, spec in PLATFORMS.items():
        out[plat] = fit_platform(plat, spec)
    with open(ROOT / "out" / "fitted_coeffs_v3.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nwrote fitted_coeffs_v3.json")
