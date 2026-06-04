"""Re-fit V1 per-platform (g, L_eff, K_us, tau, delta0/use_per_seg) by random search
on dev split. Reports yaw_rmse + cte_rmse per (platform, params)."""
from __future__ import annotations
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-04")
sys.path.insert(0, str(ROOT / "out"))
sys.path.insert(0, str(ROOT / "_shared"))
from quick_score import find_segments, platform_from, PLATFORM_SCHEMA, ALLOWED, cte_rmse_segment
from traj_metrics import integrate_trajectory


def predict_v1_paramized(sim_df, p):
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    delta_road = sim_df["delta_road_rad"].to_numpy()
    if p["use_per_seg"]:
        mask = (np.abs(yr_v0) < 0.03) & (v > 5.0)
        if mask.sum() >= 50:
            delta0 = float(np.median(delta_road[mask]))
        else:
            delta0 = p["delta0_fallback"]
    else:
        delta0 = p["delta0"]
    delta = (delta_road - delta0) * p["g"]
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)
    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (p["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


def load_platform_segments(plat):
    paths = [p for p in find_segments() if platform_from(p) == plat]
    data = []
    for p in paths:
        df = pd.read_csv(p)
        sch = PLATFORM_SCHEMA[plat]
        if sch["truth"] not in df.columns:
            continue
        sim_in = df[[c for c in df.columns if c in ALLOWED]].copy()
        if "yaw_rate_pred_rads" not in sim_in.columns:
            sim_in["yaw_rate_pred_rads"] = df[sch["baseline"]].to_numpy()
        yr_t = df[sch["truth"]].to_numpy()
        data.append((sim_in, yr_t))
    return data


def score_params(data, p):
    yaw_sq = 0.0
    yaw_n = 0
    cte_sq = 0.0
    cte_n = 0
    for sim_in, yr_t in data:
        yr_p = predict_v1_paramized(sim_in, p)
        v = sim_in["v_mps"].to_numpy()
        t = sim_in["t_s"].to_numpy()
        m = v > 2.0
        if m.any():
            res = yr_p[m] - yr_t[m]
            yaw_sq += float((res ** 2).sum())
            yaw_n += int(m.sum())
        c, n = cte_rmse_segment(t, v, yr_p, yr_t)
        if c is not None:
            cte_sq += (c ** 2) * n
            cte_n += n
    return (np.sqrt(yaw_sq / yaw_n) if yaw_n else float("nan"),
            np.sqrt(cte_sq / cte_n) if cte_n else float("nan"))


V1 = {
    "FORD_F_150_LIGHTNING_MK1": {"use_per_seg": False, "delta0": 0.00133, "delta0_fallback": 0, "g": 0.863, "L_eff": 3.26, "K_us": 0.00350, "tau": 0.060},
    "FORD_MUSTANG_MACH_E_MK1":  {"use_per_seg": True,  "delta0": 0.0,     "delta0_fallback": -0.0001, "g": 0.891, "L_eff": 2.22, "K_us": 0.00150, "tau": 0.069},
    "HYUNDAI_IONIQ_5":          {"use_per_seg": True,  "delta0": 0.0,     "delta0_fallback": 0.0,    "g": 0.938, "L_eff": 2.887, "K_us": 0.00289, "tau": 0.062},
}


def fit_platform(plat, n_trials=80, seed=0):
    rng = np.random.default_rng(seed)
    data = load_platform_segments(plat)
    print(f"[{plat}] {len(data)} segments")
    base = V1[plat]
    base_y, base_c = score_params(data, base)
    print(f"  V1 baseline: yaw={base_y:.6f}  cte={base_c:.4f}")
    # Weighted objective: scale CTE so improvements both matter.
    best = (base_y / base_y + base_c / base_c, base, base_y, base_c)
    for _ in range(n_trials):
        cand = dict(base)
        cand["g"]     = base["g"]     * float(rng.uniform(0.92, 1.08))
        cand["L_eff"] = base["L_eff"] * float(rng.uniform(0.93, 1.10))
        cand["K_us"]  = max(0.0, base["K_us"] * float(rng.uniform(0.3, 2.5)))
        cand["tau"]   = max(0.005, base["tau"] * float(rng.uniform(0.4, 2.0)))
        cand["delta0_fallback"] = base["delta0_fallback"] + float(rng.uniform(-0.003, 0.003))
        cand["delta0"] = base["delta0"] + float(rng.uniform(-0.003, 0.003))
        y, c = score_params(data, cand)
        if not np.isfinite(y) or not np.isfinite(c):
            continue
        obj = y / base_y + c / base_c
        if obj < best[0]:
            best = (obj, cand, y, c)
    print(f"  best: yaw={best[2]:.6f}  cte={best[3]:.4f}")
    return best[1], best[2], best[3]


if __name__ == "__main__":
    out = {}
    for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]:
        params, y, c = fit_platform(plat, n_trials=120, seed=1)
        out[plat] = {"params": params, "yaw_rmse": y, "cte_rmse": c}
    with open(ROOT / "out" / "fit_v1_params.json", "w") as f:
        json.dump(out, f, indent=2)
    print("wrote fit_v1_params.json")
