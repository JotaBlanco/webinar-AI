"""Fit with L_eff CONSTRAINED to known wheelbase (per anti-patterns advice
on g x L_eff scale invariance)."""

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


# Known/typical wheelbases (m). References & manufacturer specs.
# Mach-E: ~2.984 m, Lightning: ~3.700 m, Ioniq 5: ~3.000 m.
L_EFF_FIXED = {
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "FORD_MUSTANG_MACH_E_MK1": 2.98,
    "HYUNDAI_IONIQ_5": 3.00,
}


def fit_platform(plat: str, use_per_seg_delta0: bool, x0=None):
    paths = find_segments(plat)
    segs = [cache_segment(p) for p in paths]
    L_eff = L_EFF_FIXED[plat]
    print(f"[{plat}] {len(segs)} segs, L_eff fixed at {L_eff}")
    if not segs:
        return None

    if x0 is None:
        x0 = np.array([0.88, 0.0025, 0.065, 0.0005])

    def loss(x):
        g, K_us, tau, delta0_glob = x
        if tau < 0.005 or K_us < 0 or g < 0.3 or g > 1.5:
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
                   options={"xatol": 1e-6, "fatol": 1e-12, "maxiter": 2000})
    dt_fit = time.time() - t0
    g, K_us, tau, delta0_glob = res.x
    rmse = math.sqrt(res.fun)
    print(f"  fit ({dt_fit:.1f}s, {res.nit} iter): g={g:.4f} L_eff={L_eff:.3f} "
          f"K_us={K_us:.5f} tau={tau:.4f} delta0={delta0_glob:.6f}")
    print(f"  train yaw RMSE = {rmse:.6f}")
    return {
        "g": float(g), "L_eff": float(L_eff), "K_us": float(K_us),
        "tau": float(tau), "delta0_glob": float(delta0_glob),
        "use_per_segment_delta0": use_per_seg_delta0,
        "train_yaw_rmse": rmse,
    }


if __name__ == "__main__":
    plat_cfg = {
        "FORD_F_150_LIGHTNING_MK1": False,
        "FORD_MUSTANG_MACH_E_MK1": True,
        "HYUNDAI_IONIQ_5": False,
    }
    results = {}
    for plat, use_per_seg in plat_cfg.items():
        r = fit_platform(plat, use_per_seg)
        if r:
            results[plat] = r
    out_path = ROOT / "out" / "coeffs_fit_v3.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"Wrote {out_path}")
