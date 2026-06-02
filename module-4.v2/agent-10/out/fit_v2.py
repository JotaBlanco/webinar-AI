"""Fit a V2 predict: V1 plus
- per-platform yaw bias (residual mean)
- nonlinear understeer: K_us(|delta|) = K_us + K_us2 * delta^2 (cubic in steady-state yaw)
- additional feedforward feature: a small linear correction proportional to v*ddelta/dt
  (captures transient steering lag mismatch)

Optimize a small parameter set per platform using scipy minimize.
"""
from __future__ import annotations
import sys
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-10")
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "_shared"))
from v1_baseline import PLATFORM_PARAMS_V1, _per_segment_delta0

DATA_SIM = ROOT / "data" / "sim" / "segments"


def list_segments(platform):
    plat_dir = DATA_SIM / platform
    out = []
    for route_dir in sorted(plat_dir.iterdir()):
        if not route_dir.is_dir():
            continue
        for sub in sorted(route_dir.iterdir()):
            if not sub.is_dir():
                continue
            for seg in sorted(sub.iterdir()):
                f = seg / "sim.csv"
                if f.is_file():
                    out.append(f)
    return out


def load_segment(f):
    df = pd.read_csv(f)
    return df


def predict_v2_one(df, params, delta0):
    g = params["g"]
    L = params["L_eff"]
    K_us = params["K_us"]
    K_us2 = params.get("K_us2", 0.0)
    tau = params["tau"]
    bias = params.get("bias", 0.0)
    k_ff = params.get("k_ff", 0.0)
    delta_road = df["delta_road_rad"].to_numpy()
    delta = (delta_road - delta0) * g
    v = df["v_mps"].to_numpy()
    t = df["t_s"].to_numpy()
    # Nonlinear understeer denominator: include K_us2 * v^2 * delta^2 term
    denom = L + K_us * v * v + K_us2 * v * v * delta * delta
    yr_ss = v * delta / denom
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    # Feedforward: small term proportional to v * d(delta)/dt
    if k_ff != 0.0:
        ddelta = np.gradient(delta_road, t)
        yr = yr + k_ff * v * ddelta
    return yr + bias


def loss_for_platform(platform, segments, fit_params):
    p = dict(PLATFORM_PARAMS_V1[platform])
    p.update(fit_params)
    sse = 0.0
    n = 0
    for df, delta0, truth in segments:
        pred = predict_v2_one(df, p, delta0)
        d = pred - truth
        sse += float(np.sum(d * d))
        n += len(d)
    return math.sqrt(sse / n)


def fit_platform(platform, max_segments=120):
    p0 = PLATFORM_PARAMS_V1[platform]
    files = list_segments(platform)[:max_segments]
    segments = []
    for f in files:
        df = load_segment(f)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        if p0["use_per_segment_delta0"]:
            # Use V0 yaw_rate_pred for the mask just like v1_baseline does
            delta0 = _per_segment_delta0(df, fallback=p0["delta0_fallback"])
        else:
            delta0 = p0["delta0"]
        segments.append((df, delta0, df["yaw_rate_meas_rads"].to_numpy()))

    # Initial point: V1 coefficients + zero bias + zero K_us2 + zero k_ff
    x0 = np.array([p0["g"], p0["L_eff"], p0["K_us"], p0["tau"], 0.0, 0.0, 0.0])

    def unpack(x):
        return {"g": x[0], "L_eff": x[1], "K_us": x[2], "tau": max(x[3], 0.005),
                "K_us2": x[4], "bias": x[5], "k_ff": x[6]}

    def obj(x):
        try:
            return loss_for_platform(platform, segments, unpack(x))
        except Exception:
            return 1e6

    # Reasonable bounds
    bounds = [
        (max(p0["g"] - 0.15, 0.5), p0["g"] + 0.15),
        (max(p0["L_eff"] - 1.0, 1.5), p0["L_eff"] + 1.0),
        (max(p0["K_us"] - 0.01, 0.0), p0["K_us"] + 0.01),
        (0.005, 0.3),
        (-5.0, 5.0),
        (-0.02, 0.02),
        (-0.05, 0.05),
    ]
    res = minimize(obj, x0, method="L-BFGS-B", bounds=bounds, options={"maxiter": 200, "ftol": 1e-9})
    fit = unpack(res.x)
    rmse_v1 = loss_for_platform(platform, segments,
                                 {"g": p0["g"], "L_eff": p0["L_eff"], "K_us": p0["K_us"],
                                  "tau": p0["tau"], "K_us2": 0.0, "bias": 0.0, "k_ff": 0.0})
    rmse_v2 = loss_for_platform(platform, segments, fit)
    print(f"{platform}: V1 fit-set rmse={rmse_v1:.5f} -> V2 rmse={rmse_v2:.5f}")
    print(f"  params: {fit}")
    return fit


def main():
    coeffs = {}
    for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]:
        fit = fit_platform(plat, max_segments=150)
        # Preserve delta0 strategy from v1
        p0 = PLATFORM_PARAMS_V1[plat]
        out = {
            "g": fit["g"], "L_eff": fit["L_eff"], "K_us": fit["K_us"],
            "tau": fit["tau"], "K_us2": fit["K_us2"], "bias": fit["bias"], "k_ff": fit["k_ff"],
            "use_per_segment_delta0": p0["use_per_segment_delta0"],
            "delta0": p0.get("delta0", 0.0),
            "delta0_fallback": p0.get("delta0_fallback", 0.0),
        }
        coeffs[plat] = out
    out_path = ROOT / "out" / "v2_coeffs.json"
    out_path.write_text(json.dumps(coeffs, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
