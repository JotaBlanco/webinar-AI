"""V2: V1 + per-platform yaw bias + steering-derivative gain.

Attacks two of V1's residuals:
  1. Per-platform CTE drift  ->  additive bias `b`.
  2. Transient-regime yaw error -> additive `k_dd * d(delta_road)/dt`.

Scans (b, k_dd) jointly per platform, starting from analytical optimum from V2.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "_shared"))

from score import score  # noqa: E402
from v1_baseline import predict_v1  # noqa: E402


PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]


def make_predict(bias_by, kdd_by):
    def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
        out = predict_v1(sim_df, platform).copy()
        yr = out["yaw_rate_pred_rads"].to_numpy(dtype=float)
        b = bias_by.get(platform, 0.0)
        k = kdd_by.get(platform, 0.0)
        yr = yr + b
        if k != 0.0 and "delta_road_rad" in sim_df.columns:
            t = sim_df["t_s"].to_numpy(dtype=float)
            d = sim_df["delta_road_rad"].to_numpy(dtype=float)
            if len(t) >= 2:
                dd = np.gradient(d, t)
                yr = yr + k * dd
        out["yaw_rate_pred_rads"] = yr
        return out
    return predict


def main():
    # Load V1 baseline.
    print("Scoring V1...")
    r0 = score(predict_v1)
    print(f"V1 pooled: yaw={r0['yaw_rate_rmse']:.5f}, cte={r0['cte_rmse']:.3f}")

    # Start from previously fit biases.
    start_bias = {
        "FORD_F_150_LIGHTNING_MK1": -0.00012,
        "FORD_MUSTANG_MACH_E_MK1": +0.00213,
        "HYUNDAI_IONIQ_5": +0.00112,
    }

    results = {}
    for plat in PLATFORMS:
        print(f"\n=== {plat}: scan k_dd at fixed bias ===")
        # Sweep k_dd at the current best bias.
        v1_yaw = r0["per_platform"][plat]["yaw_rate_rmse"]
        v1_cte = r0["per_platform"][plat]["cte_rmse"]
        best = None
        kdd_grid = [-0.2, -0.1, -0.05, -0.02, -0.01, 0.0, 0.01, 0.02, 0.05, 0.1, 0.2]
        for k in kdd_grid:
            bias_by = {p: 0.0 for p in PLATFORMS}
            kdd_by = {p: 0.0 for p in PLATFORMS}
            bias_by[plat] = start_bias[plat]
            kdd_by[plat] = k
            pf = make_predict(bias_by, kdd_by)
            r = score(pf, platform_filter=plat)
            combined = r["yaw_rate_rmse"] / v1_yaw + r["cte_rmse"] / v1_cte
            print(f"  k_dd={k:+.3f}: yaw={r['yaw_rate_rmse']:.5f}, cte={r['cte_rmse']:.3f}, combined={combined:.4f}")
            if best is None or combined < best["combined"]:
                best = {"bias": start_bias[plat], "k_dd": k,
                        "yaw_rmse": r["yaw_rate_rmse"], "cte_rmse": r["cte_rmse"],
                        "combined": combined}
        results[plat] = best
        print(f"  BEST: bias={best['bias']:+.5f}, k_dd={best['k_dd']:+.3f}")

    # Final pooled
    bias_by = {p: results[p]["bias"] for p in PLATFORMS}
    kdd_by = {p: results[p]["k_dd"] for p in PLATFORMS}
    pf = make_predict(bias_by, kdd_by)
    print("\nFinal pooled:")
    r_final = score(pf)
    print(f"  yaw_rmse: {r_final['yaw_rate_rmse']:.5f} (V1: {r0['yaw_rate_rmse']:.5f})")
    print(f"  cte_rmse: {r_final['cte_rmse']:.4f} (V1: {r0['cte_rmse']:.4f})")
    for p in PLATFORMS:
        m = r_final["per_platform"][p]
        v = r0["per_platform"][p]
        print(f"  {p}: yaw {v['yaw_rate_rmse']:.5f}->{m['yaw_rate_rmse']:.5f}, "
              f"cte {v['cte_rmse']:.3f}->{m['cte_rmse']:.3f}")

    coeffs = {
        "yaw_bias_by_platform": bias_by,
        "kdd_by_platform": kdd_by,
        "diagnostics": results,
        "pooled_final": {
            "yaw_rate_rmse": r_final["yaw_rate_rmse"],
            "cte_rmse": r_final["cte_rmse"],
        },
    }
    out_path = ROOT / "out" / "coeffs_v2.json"
    with out_path.open("w") as fh:
        json.dump(coeffs, fh, indent=2, default=float)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
