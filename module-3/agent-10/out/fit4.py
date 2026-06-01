"""Fit4 — relax g bound, try per-segment delta0 on all platforms.

We sweep (use_per_seg_delta0 in {False, True}) and pick the lower train yaw RMSE.
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-10")
sys.path.insert(0, str(ROOT / "out"))
from fit2 import find_segments, cache_segment, predict_yaw_fast  # noqa: E402


def fit_one(plat: str, use_per_seg_delta0: bool, x0=None, verbose=True):
    paths = find_segments(plat)
    segs = [cache_segment(p) for p in paths]
    if not segs:
        return None

    if x0 is None:
        x0 = np.array([1.0, 3.0, 0.0025, 0.065, 0.0005])

    def loss(x):
        g, L_eff, K_us, tau, delta0_glob = x
        if L_eff < 1.5 or L_eff > 6.0 or tau < 0.005 or tau > 0.5 or K_us < 0 or g < 0.3 or g > 3.0:
            return 1e9
        sum_sq = 0.0
        n = 0
        for s in segs:
            d0 = (s["d0_segment"] if (use_per_seg_delta0 and s["d0_segment"] is not None)
                  else delta0_glob)
            yr = predict_yaw_fast(s, g, L_eff, K_us, tau, d0)
            r = yr - s["yr_truth"]
            sum_sq += float((r * r).sum())
            n += len(r)
        return sum_sq / n

    t0 = time.time()
    res = minimize(loss, x0, method="Nelder-Mead",
                   options={"xatol": 1e-6, "fatol": 1e-12, "maxiter": 3000})
    dt_fit = time.time() - t0
    g, L_eff, K_us, tau, delta0_glob = res.x
    rmse = math.sqrt(res.fun)
    if verbose:
        print(f"  [{plat} use_per_seg={use_per_seg_delta0}] ({dt_fit:.1f}s, {res.nit} iter): "
              f"g={g:.4f} L_eff={L_eff:.3f} K_us={K_us:.5f} tau={tau:.4f} delta0={delta0_glob:.6f} "
              f"-> RMSE {rmse:.6f}")
    return {
        "g": float(g), "L_eff": float(L_eff), "K_us": float(K_us),
        "tau": float(tau), "delta0_glob": float(delta0_glob),
        "use_per_segment_delta0": use_per_seg_delta0,
        "train_yaw_rmse": rmse,
    }


if __name__ == "__main__":
    platforms = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]
    results = {}
    for plat in platforms:
        print(f"=== {plat} ===")
        best = None
        for use_per_seg in (False, True):
            r = fit_one(plat, use_per_seg)
            if r is None:
                continue
            if best is None or r["train_yaw_rmse"] < best["train_yaw_rmse"]:
                best = r
        results[plat] = best
        print(f"  >> best: use_per_seg={best['use_per_segment_delta0']} rmse={best['train_yaw_rmse']:.6f}")
    out_path = ROOT / "out" / "coeffs_fit_v4.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"Wrote {out_path}")
