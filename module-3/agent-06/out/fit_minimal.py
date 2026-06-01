"""Minimal targeted refinement for Mach-E and Ioniq using small subsample.

Strategy: tweak only K_us and delta0/delta0_fallback (the bias movers).
g, L_eff, tau stay at priors. Use 60 random segments per platform.
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
sys.path.insert(0, str(ROOT / "final-model"))

from traj_metrics import cte_diagnostics_segment  # noqa: E402
from predict import _predict_yaw  # noqa: E402

N_TRAIN = 60
SEED = 7

PLATFORM_TRUTH = {
    "FORD_F_150_LIGHTNING_MK1": "yaw_rate_meas_rads",
    "FORD_MUSTANG_MACH_E_MK1":  "yaw_rate_meas_rads",
    "HYUNDAI_IONIQ_5":          "yaw_rate_meas_rads",
}


def load(platform):
    truth = PLATFORM_TRUTH[platform]
    base = ROOT / "data" / "sim" / "segments" / platform
    paths = sorted(p for p in base.glob("*/**/sim.csv") if p.is_file())
    rng = np.random.default_rng(SEED)
    if len(paths) > N_TRAIN:
        idx = rng.choice(len(paths), N_TRAIN, replace=False)
        paths = [paths[i] for i in sorted(idx)]
    segs = []
    needed = {"t_s", "delta_road_rad", "v_mps", truth}
    for p in paths:
        df = pd.read_csv(p, usecols=lambda c: c in needed)
        if not needed <= set(df.columns):
            continue
        t = df["t_s"].to_numpy(float)
        if len(t) < 50 or np.any(np.diff(t) <= 0):
            continue
        segs.append((t, df["v_mps"].to_numpy(float),
                     df["delta_road_rad"].to_numpy(float),
                     df[truth].to_numpy(float),
                     p))
    return segs


def eval_(coeffs, segs, lam_cte=0.0003):
    yaw_sq = 0.0
    yaw_n = 0
    cte_sq = 0.0
    cte_n = 0
    for t, v, d, tr, _ in segs:
        sim_df = pd.DataFrame({"t_s": t, "delta_road_rad": d, "v_mps": v})
        yp = _predict_yaw(sim_df, coeffs)
        mask = v > 2.0
        if mask.any():
            r = (yp - tr)[mask]
            yaw_sq += float(np.dot(r, r))
            yaw_n += int(mask.sum())
        cd = cte_diagnostics_segment(t, v, tr, yp, grid_step_m=1.0, min_distance_m=20.0)
        cte_sq += cd["sum_sq_m2"]
        cte_n += cd["n_bins"]
    yaw = math.sqrt(yaw_sq / yaw_n) if yaw_n else float("nan")
    cte = math.sqrt(cte_sq / cte_n) if cte_n else float("nan")
    return yaw, cte, yaw + lam_cte * cte


def refine(platform, base_coeffs, keys, bounds, maxiter=80):
    print(f"\n=== refining {platform} on keys {keys} ===")
    t0 = time.time()
    segs = load(platform)
    print(f"  {len(segs)} train segments loaded in {time.time()-t0:.1f}s")

    x0 = np.array([base_coeffs[k] for k in keys], dtype=float)
    lo = np.array([bounds[k][0] for k in keys], dtype=float)
    hi = np.array([bounds[k][1] for k in keys], dtype=float)

    def obj(x):
        if np.any(x < lo) or np.any(x > hi):
            return 1e6
        c = dict(base_coeffs)
        for i, k in enumerate(keys):
            c[k] = float(x[i])
        # keep fallback in sync with delta0 if both relevant
        if "delta0" in keys and "delta0_fallback" in c:
            c["delta0_fallback"] = c["delta0"]
        yaw, cte, loss = eval_(c, segs)
        if not math.isfinite(loss):
            return 1e6
        return loss

    t1 = time.time()
    res = minimize(obj, x0, method="Nelder-Mead",
                   options={"xatol": 1e-6, "fatol": 1e-6,
                            "maxiter": maxiter, "adaptive": True})
    print(f"  optim {time.time()-t1:.1f}s, nit={res.nit}, nfev={res.nfev}")
    x = np.clip(res.x, lo, hi)
    c = dict(base_coeffs)
    for i, k in enumerate(keys):
        c[k] = float(x[i])
    if "delta0" in keys and "delta0_fallback" in c:
        c["delta0_fallback"] = c["delta0"]
    yaw, cte, _ = eval_(c, segs)
    print(f"  new: yaw={yaw:.5f} cte={cte:.3f}  coeffs={c}")
    return c


def main():
    coeffs_path = ROOT / "final-model" / "coeffs.json"
    coeffs = json.loads(coeffs_path.read_text())

    # Mach-E: yaw_bias=-0.00132 cte=-19.7m — fit delta0_fallback, K_us, g, tau
    coeffs["FORD_MUSTANG_MACH_E_MK1"] = refine(
        "FORD_MUSTANG_MACH_E_MK1",
        coeffs["FORD_MUSTANG_MACH_E_MK1"],
        keys=["delta0", "K_us", "g", "tau"],
        bounds={"delta0": (-0.02, 0.02), "K_us": (0.0, 0.02),
                "g": (0.6, 1.2), "tau": (0.005, 0.3)},
    )

    # Ioniq: cte=-6.6m, yaw bias modest. Fit delta0, K_us, g, tau, L_eff
    coeffs["HYUNDAI_IONIQ_5"] = refine(
        "HYUNDAI_IONIQ_5",
        coeffs["HYUNDAI_IONIQ_5"],
        keys=["delta0", "K_us", "g", "tau", "L_eff"],
        bounds={"delta0": (-0.02, 0.02), "K_us": (0.0, 0.02),
                "g": (0.6, 1.2), "tau": (0.005, 0.3),
                "L_eff": (2.3, 3.8)},
    )

    # Lightning is already excellent (yaw 0.00566, cte 62, bias near 0).
    # Still — light refinement on K_us, g, tau to chase steady regime.
    coeffs["FORD_F_150_LIGHTNING_MK1"] = refine(
        "FORD_F_150_LIGHTNING_MK1",
        coeffs["FORD_F_150_LIGHTNING_MK1"],
        keys=["delta0", "K_us", "g", "tau"],
        bounds={"delta0": (-0.02, 0.02), "K_us": (0.0, 0.02),
                "g": (0.6, 1.2), "tau": (0.005, 0.3)},
    )

    coeffs_path.write_text(json.dumps(coeffs, indent=2))
    print(f"\nwrote {coeffs_path}")


if __name__ == "__main__":
    main()
