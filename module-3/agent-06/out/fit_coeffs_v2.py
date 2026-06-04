"""V2 fit — fix L_eff to physical wheelbase (eliminates g↔L scale invariance).
Fit only (g, K_us, tau, delta0). Use yaw-RMSE loss with bias-penalty for CTE.
"""
import sys, os, json, math
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-06")
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "out"))

PHYS_L = {
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "HYUNDAI_IONIQ_5": 3.0,  # standard wheelbase
}


def _per_segment_delta0(yr_v0, v, delta_road, fallback=0.0,
                        yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(np.median(delta_road[mask]))


def yaw_predict(sim_df, p, use_per_segment_delta0, delta0_fallback, L_eff):
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    delta_r = sim_df["delta_road_rad"].to_numpy()
    if use_per_segment_delta0:
        delta0 = _per_segment_delta0(yr_v0, v, delta_r, fallback=delta0_fallback)
    else:
        delta0 = delta0_fallback
    delta = (delta_r - delta0) * p["g"]
    yr_ss = v * delta / (L_eff + p["K_us"] * v * v)
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


def objective(segs, use_per_segment_delta0, L_eff, bias_weight=50.0):
    def loss(theta):
        g, K_us, tau, delta0_fallback = theta
        if not (0.5 < g < 1.3 and 0 <= K_us < 0.02
                and 0.005 < tau < 0.3 and -0.05 < delta0_fallback < 0.05):
            return 1e6
        p = {"g": g, "K_us": K_us, "tau": tau}
        sum_sq = 0.0
        sum_signed = 0.0
        n = 0
        for df in segs:
            try:
                yr = yaw_predict(df, p, use_per_segment_delta0, delta0_fallback, L_eff)
            except Exception:
                return 1e6
            v = df["v_mps"].to_numpy()
            yr_truth = df["yaw_rate_meas_rads"].to_numpy()
            mask = v > 2.0
            if not mask.any():
                continue
            r = yr[mask] - yr_truth[mask]
            sum_sq += float(np.sum(r*r))
            sum_signed += float(np.sum(r))
            n += int(mask.sum())
        if n == 0:
            return 1e6
        yaw_rmse = math.sqrt(sum_sq / n)
        bias = abs(sum_signed / n)
        return yaw_rmse + bias_weight * bias
    return loss


def fit_platform(platform, use_per_segment_delta0, x0, max_segments=100):
    print(f"\n=== Fitting {platform} (per_segment_delta0={use_per_segment_delta0}) ===")
    segs = load_platform_segments(platform, max_segments=max_segments)
    print(f"  loaded {len(segs)} training segments")
    if not segs:
        return None
    L_eff = PHYS_L[platform]
    print(f"  fixed L_eff = {L_eff}")
    loss = objective(segs, use_per_segment_delta0, L_eff)
    print(f"  loss at x0: {loss(x0):.6f}")
    res = minimize(loss, x0, method="Nelder-Mead",
                   options={"xatol": 1e-6, "fatol": 1e-7, "maxiter": 800})
    print(f"  fit result: g={res.x[0]:.4f}, K_us={res.x[1]:.5f}, tau={res.x[2]:.4f}, delta0={res.x[3]:.5f}")
    print(f"  final loss: {res.fun:.6f}")
    g, K_us, tau, delta0 = res.x
    return {
        "g": float(g), "L_eff": L_eff, "K_us": float(K_us),
        "tau": float(tau),
        "use_per_segment_delta0": bool(use_per_segment_delta0),
        ("delta0_fallback" if use_per_segment_delta0 else "delta0"): float(delta0),
    }


if __name__ == "__main__":
    fits = {}
    r = fit_platform("FORD_F_150_LIGHTNING_MK1", False,
                     x0=[0.95, 0.003, 0.060, 0.00133], max_segments=100)
    if r: fits["FORD_F_150_LIGHTNING_MK1"] = r

    r = fit_platform("FORD_MUSTANG_MACH_E_MK1", True,
                     x0=[0.95, 0.0015, 0.069, -0.0001], max_segments=100)
    if r: fits["FORD_MUSTANG_MACH_E_MK1"] = r

    r = fit_platform("HYUNDAI_IONIQ_5", True,
                     x0=[0.95, 0.0029, 0.062, 0.0], max_segments=100)
    if r: fits["HYUNDAI_IONIQ_5"] = r

    out = ROOT / "out" / "coeffs_fitted_v2.json"
    with open(out, "w") as f:
        json.dump(fits, f, indent=2)
    print(f"\nSaved to {out}")
    print(json.dumps(fits, indent=2))
