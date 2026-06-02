"""V3 fit — combined yaw RMSE + scaled CTE RMSE loss, per platform.

Same model form as V2 but the loss is a weighted sum of pooled yaw RMSE and
pooled CTE RMSE (CTE is much larger numerically, so we down-weight it).
"""
from __future__ import annotations
import sys, json, math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-10")
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "_shared"))
from v1_baseline import PLATFORM_PARAMS_V1, _per_segment_delta0
from traj_metrics import cte_rmse_segment

DATA_SIM = ROOT / "data" / "sim" / "segments"


def list_segments(platform, limit=None):
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
                    if limit and len(out) >= limit:
                        return out
    return out


def predict_v2_one(df, params, delta0):
    g = params["g"]; L = params["L_eff"]; K_us = params["K_us"]
    K_us2 = params.get("K_us2", 0.0); tau = max(params["tau"], 1e-3)
    bias = params.get("bias", 0.0); k_ff = params.get("k_ff", 0.0)
    delta_road = df["delta_road_rad"].to_numpy()
    delta = (delta_road - delta0) * g
    v = df["v_mps"].to_numpy(); t = df["t_s"].to_numpy()
    denom = L + K_us * v * v + K_us2 * v * v * delta * delta
    denom = np.where(denom < 0.1, 0.1, denom)
    yr_ss = v * delta / denom
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss); yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    if k_ff != 0.0:
        ddelta = np.gradient(delta_road, t)
        yr = yr + k_ff * v * ddelta
    return yr + bias


def joint_loss(platform, segments, params, w_cte=1.0):
    yaw_sse = 0.0; yaw_n = 0
    cte_sse = 0.0; cte_n = 0
    for df, delta0, truth, t, v in segments:
        pred = predict_v2_one(df, params, delta0)
        d = pred - truth
        yaw_sse += float((d * d).sum()); yaw_n += len(d)
        sum_sq, n_bins, _ = cte_rmse_segment(t, v, truth, pred)
        cte_sse += sum_sq; cte_n += n_bins
    yaw_rmse = math.sqrt(yaw_sse / max(yaw_n, 1))
    cte_rmse = math.sqrt(cte_sse / max(cte_n, 1)) if cte_n else 0.0
    # Normalise scales: yaw_rmse ~ 0.01, cte_rmse ~ 70.  We want both to count;
    # divide cte by 70 so the two terms are comparable.
    return yaw_rmse + w_cte * (cte_rmse / 70.0) * 0.01


def fit_platform(platform, max_segments=150, w_cte=1.0):
    p0 = PLATFORM_PARAMS_V1[platform]
    files = list_segments(platform, limit=max_segments)
    segments = []
    for f in files:
        df = pd.read_csv(f)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        delta0 = (_per_segment_delta0(df, fallback=p0["delta0_fallback"])
                  if p0["use_per_segment_delta0"] else p0["delta0"])
        truth = df["yaw_rate_meas_rads"].to_numpy()
        t = df["t_s"].to_numpy()
        v = df["v_mps"].to_numpy()
        segments.append((df, delta0, truth, t, v))

    x0 = np.array([p0["g"], p0["L_eff"], p0["K_us"], p0["tau"], 0.0, 0.0, 0.0])

    def unpack(x):
        return {"g": x[0], "L_eff": x[1], "K_us": x[2], "tau": max(x[3], 0.005),
                "K_us2": x[4], "bias": x[5], "k_ff": x[6]}

    def obj(x):
        try:
            return joint_loss(platform, segments, unpack(x), w_cte=w_cte)
        except Exception:
            return 1e6

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
    base = joint_loss(platform, segments,
                       {"g": p0["g"], "L_eff": p0["L_eff"], "K_us": p0["K_us"],
                        "tau": p0["tau"], "K_us2": 0.0, "bias": 0.0, "k_ff": 0.0},
                       w_cte=w_cte)
    new = joint_loss(platform, segments, fit, w_cte=w_cte)
    print(f"{platform}: V1 joint={base:.6f} -> V3 joint={new:.6f}")
    print(f"  params: {fit}")
    return fit


def main():
    coeffs = {}
    for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]:
        fit = fit_platform(plat, max_segments=120, w_cte=1.0)
        p0 = PLATFORM_PARAMS_V1[plat]
        coeffs[plat] = {
            "g": fit["g"], "L_eff": fit["L_eff"], "K_us": fit["K_us"],
            "tau": fit["tau"], "K_us2": fit["K_us2"], "bias": fit["bias"],
            "k_ff": fit["k_ff"],
            "use_per_segment_delta0": p0["use_per_segment_delta0"],
            "delta0": p0.get("delta0", 0.0),
            "delta0_fallback": p0.get("delta0_fallback", 0.0),
        }
    (ROOT / "out" / "v3_coeffs.json").write_text(json.dumps(coeffs, indent=2))
    print("\nWrote v3_coeffs.json")


if __name__ == "__main__":
    main()
