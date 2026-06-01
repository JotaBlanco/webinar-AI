"""Fast per-platform fit using a sub-sample and tighter Nelder-Mead.

Strategy:
- Use up to N_TRAIN segments per platform (random sample, seeded for repro).
- Loss = yaw_rmse + lam * cte_rmse on the training subset.
- Nelder-Mead, max ~150 iterations.
- Pre-compute v, delta, t arrays once.
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-06")
sys.path.insert(0, str(ROOT / "_shared"))
from traj_metrics import cte_diagnostics_segment  # noqa: E402

PLATFORM_TRUTH = {
    "FORD_F_150_LIGHTNING_MK1": "yaw_rate_meas_rads",
    "FORD_MUSTANG_MACH_E_MK1":  "yaw_rate_meas_rads",
    "HYUNDAI_IONIQ_5":          "yaw_rate_meas_rads",
}

N_TRAIN = 120         # segments sampled per platform for fitting
SEED = 1234
LAM_CTE = 0.0003      # weight on cte_rmse in scalar loss


def _per_segment_delta0(delta_road, v, delta_thresh=0.005, v_thresh=5.0,
                        min_rows=50, fallback=0.0):
    mask = (np.abs(delta_road) < delta_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(np.median(delta_road[mask]))


def _predict_yaw_arr(t, v, delta_road, p):
    if p.get("use_per_segment_delta0", False):
        delta0 = _per_segment_delta0(
            delta_road, v,
            delta_thresh=p.get("delta0_detect_thresh", 0.005),
            v_thresh=5.0, min_rows=50,
            fallback=p.get("delta0_fallback", p.get("delta0", 0.0)),
        )
    else:
        delta0 = float(p["delta0"])

    delta = (delta_road - delta0) * float(p["g"])
    L_eff = float(p["L_eff"])
    K_us = float(p["K_us"])
    yr_ss = v * delta / (L_eff + K_us * v * v)

    tau = max(float(p["tau"]), 1e-4)
    dt = np.diff(t, prepend=t[0])
    if dt[0] <= 0 and len(dt) > 1:
        dt[0] = float(np.median(dt[1:]))
    alpha = dt / (tau + dt)

    n = len(yr_ss)
    yr = np.empty(n)
    yr[0] = yr_ss[0]
    for i in range(1, n):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


def load_platform_segments(platform: str, n_sample: int | None = None) -> list[dict]:
    truth = PLATFORM_TRUTH[platform]
    base = ROOT / "data" / "sim" / "segments" / platform
    paths = sorted(p for p in base.glob("*/**/sim.csv") if p.is_file())
    if n_sample and len(paths) > n_sample:
        rng = np.random.default_rng(SEED)
        idx = rng.choice(len(paths), n_sample, replace=False)
        paths = [paths[i] for i in sorted(idx)]
    segs = []
    needed = {"t_s", "delta_road_rad", "v_mps", truth}
    for p in paths:
        try:
            df = pd.read_csv(p, usecols=lambda c: c in needed)
        except Exception:
            continue
        if not needed <= set(df.columns):
            continue
        t = df["t_s"].to_numpy(dtype=float)
        if len(t) < 50 or np.any(np.diff(t) <= 0):
            continue
        segs.append({
            "t":     t,
            "v":     df["v_mps"].to_numpy(dtype=float),
            "delta": df["delta_road_rad"].to_numpy(dtype=float),
            "truth": df[truth].to_numpy(dtype=float),
        })
    return segs


def eval_platform(p: dict, segs: list[dict], v_thresh=2.0,
                  grid_step_m=1.0, min_distance_m=20.0):
    yaw_sum_sq = 0.0
    yaw_n = 0
    cte_sum_sq = 0.0
    cte_n = 0
    for seg in segs:
        yr_pred = _predict_yaw_arr(seg["t"], seg["v"], seg["delta"], p)
        mask = seg["v"] > v_thresh
        if mask.any():
            r = (yr_pred - seg["truth"])[mask]
            yaw_sum_sq += float(np.dot(r, r))
            yaw_n += int(mask.sum())
        cte = cte_diagnostics_segment(
            seg["t"], seg["v"], seg["truth"], yr_pred,
            grid_step_m=grid_step_m, min_distance_m=min_distance_m,
        )
        cte_sum_sq += cte["sum_sq_m2"]
        cte_n += cte["n_bins"]
    yaw_rmse = math.sqrt(yaw_sum_sq / yaw_n) if yaw_n > 0 else float("nan")
    cte_rmse = math.sqrt(cte_sum_sq / cte_n) if cte_n > 0 else float("nan")
    return yaw_rmse, cte_rmse


def fit_platform(platform: str,
                 use_per_segment_delta0: bool,
                 initial: dict, bounds: dict,
                 maxiter: int = 150):
    print(f"\n=== fitting {platform} (per_seg_delta0={use_per_segment_delta0}) ===")
    t0 = time.time()
    segs = load_platform_segments(platform, n_sample=N_TRAIN)
    print(f"  loaded {len(segs)} training segments in {time.time()-t0:.1f}s")

    keys = ["g", "delta0", "K_us", "L_eff", "tau"]
    x0 = np.array([initial[k] for k in keys], dtype=float)
    lo = np.array([bounds[k][0] for k in keys], dtype=float)
    hi = np.array([bounds[k][1] for k in keys], dtype=float)

    def to_coeffs(x):
        c = {k: float(x[i]) for i, k in enumerate(keys)}
        c["use_per_segment_delta0"] = use_per_segment_delta0
        if use_per_segment_delta0:
            c["delta0_fallback"] = c["delta0"]
        return c

    n_evals = [0]
    def obj(x):
        if np.any(x < lo) or np.any(x > hi):
            return 1e6
        c = to_coeffs(x)
        yaw, cte = eval_platform(c, segs)
        if not math.isfinite(yaw) or not math.isfinite(cte):
            return 1e6
        loss = yaw + LAM_CTE * cte
        n_evals[0] += 1
        if n_evals[0] % 20 == 0:
            print(f"    eval {n_evals[0]:>3d}: yaw={yaw:.5f} cte={cte:.3f} loss={loss:.5f}")
        return loss

    t1 = time.time()
    res = minimize(obj, x0, method="Nelder-Mead",
                   options={"xatol": 1e-5, "fatol": 1e-5,
                            "maxiter": maxiter, "disp": False, "adaptive": True})
    print(f"  optimisation done in {time.time()-t1:.1f}s, {n_evals[0]} evals, success={res.success}")
    x = np.clip(res.x, lo, hi)
    fitted = to_coeffs(x)
    yaw, cte = eval_platform(fitted, segs)
    print(f"  fitted: yaw={yaw:.5f} cte={cte:.3f}  coeffs={fitted}")
    return fitted, (yaw, cte)


DEFAULTS = {
    "FORD_F_150_LIGHTNING_MK1": {
        "use_per_segment_delta0": False,
        "initial": {"g": 0.863, "delta0": 0.00133, "K_us": 0.00350, "L_eff": 3.26, "tau": 0.060},
        "bounds":  {"g": (0.4, 1.4), "delta0": (-0.02, 0.02), "K_us": (0.0, 0.02),
                    "L_eff": (2.5, 4.5), "tau": (0.005, 0.5)},
    },
    "FORD_MUSTANG_MACH_E_MK1": {
        "use_per_segment_delta0": True,
        "initial": {"g": 0.891, "delta0": -0.0001, "K_us": 0.00202, "L_eff": 2.22, "tau": 0.069},
        "bounds":  {"g": (0.4, 1.4), "delta0": (-0.02, 0.02), "K_us": (0.0, 0.02),
                    "L_eff": (1.8, 3.5), "tau": (0.005, 0.5)},
    },
    "HYUNDAI_IONIQ_5": {
        "use_per_segment_delta0": True,  # we'll let diagnostic decide later
        "initial": {"g": 0.9, "delta0": 0.0, "K_us": 0.003, "L_eff": 3.0, "tau": 0.060},
        "bounds":  {"g": (0.4, 1.4), "delta0": (-0.02, 0.02), "K_us": (0.0, 0.02),
                    "L_eff": (2.3, 3.8), "tau": (0.005, 0.5)},
    },
}


def main():
    out = {}
    summary = []
    for plat, cfg in DEFAULTS.items():
        fitted, (yaw, cte) = fit_platform(
            plat, cfg["use_per_segment_delta0"], cfg["initial"], cfg["bounds"],
            maxiter=150,
        )
        out[plat] = fitted
        summary.append((plat, yaw, cte))
    out["TESLA_MODEL_3"] = {"passthrough": True}

    coeffs_path = ROOT / "final-model" / "coeffs.json"
    coeffs_path.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {coeffs_path}")
    for plat, yaw, cte in summary:
        print(f"  {plat:>30s}: yaw={yaw:.5f}  cte={cte:.3f}")


if __name__ == "__main__":
    main()
