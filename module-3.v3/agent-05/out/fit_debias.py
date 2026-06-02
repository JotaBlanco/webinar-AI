"""Fit a per-platform yaw-rate bias offset on top of V1.

Approach:
 1. Run V1 once across all segments, collect per-segment residuals & integration data.
 2. Analytically choose bias for each platform that jointly improves yaw_rmse + cte_rmse.

We do a small targeted scan (5 candidate biases around the analytical
yaw-only and cte-only optima) and pick the best on a combined score.
"""

from __future__ import annotations

import json
import math
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


def make_predict_with_bias(bias_by_plat: dict):
    def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
        out = predict_v1(sim_df, platform).copy()
        b = bias_by_plat.get(platform, 0.0)
        yr = out["yaw_rate_pred_rads"].to_numpy(dtype=float)
        out["yaw_rate_pred_rads"] = yr + b
        return out

    return predict


def main():
    # Baseline V1 measurement to get analytical starting biases.
    print("Scoring V1 baseline...")
    r0 = score(predict_v1)
    print(f"V1: yaw={r0['yaw_rate_rmse']:.5f}, cte={r0['cte_rmse']:.3f}")

    starting_biases = {}
    for plat in PLATFORMS:
        m = r0["per_platform"][plat]
        # Optimum for yaw RMSE: subtract mean residual.
        yaw_bias_opt = -m["yaw_residual_mean"]
        # Approx CTE-zeroing bias: cte_signed_mean accumulates roughly as bias * distance/v
        # Just use yaw_bias_opt as starting candidate.
        starting_biases[plat] = yaw_bias_opt
        print(f"  {plat}: yaw_residual_mean={m['yaw_residual_mean']:+.5f}, "
              f"cte_signed={m['cte_signed_mean']:+.3f}, start_bias={yaw_bias_opt:+.5f}")

    # Scan a small grid around the analytical optimum per platform.
    results = {}
    for plat in PLATFORMS:
        center = starting_biases[plat]
        # Wider grid: 9 points spanning ±2× the analytical optimum, plus 0.
        if abs(center) > 1e-5:
            spread = max(abs(center) * 2.0, 0.001)
        else:
            spread = 0.001
        grid = np.linspace(center - spread, center + spread, 9)
        grid = np.unique(np.round(np.concatenate([grid, [0.0, center]]), 6))

        print(f"\n=== {plat} ===")
        rows = []
        for b in grid:
            bias_by = {p: 0.0 for p in PLATFORMS}
            bias_by[plat] = float(b)
            pf = make_predict_with_bias(bias_by)
            r = score(pf, platform_filter=plat)
            rec = {
                "bias": float(b),
                "yaw_rmse": r["yaw_rate_rmse"],
                "cte_rmse": r["cte_rmse"],
                "cte_signed": r["per_platform"][plat]["cte_signed_mean"],
                "yaw_bias": r["per_platform"][plat]["yaw_residual_mean"],
            }
            rows.append(rec)
            print(f"  b={b:+.5f}: yaw_rmse={rec['yaw_rmse']:.5f}, cte_rmse={rec['cte_rmse']:.3f}, cte_signed={rec['cte_signed']:+.3f}")

        # Compute V1 cte_rmse for this platform to normalise the combined metric.
        v1_yaw = r0["per_platform"][plat]["yaw_rate_rmse"]
        v1_cte = r0["per_platform"][plat]["cte_rmse"]
        # Pick by min(yaw_rmse/v1 + cte_rmse/v1).
        for rec in rows:
            rec["combined"] = rec["yaw_rmse"] / v1_yaw + rec["cte_rmse"] / v1_cte
        rows.sort(key=lambda x: x["combined"])
        best = rows[0]
        print(f"  BEST: bias={best['bias']:+.5f} -> yaw_rmse={best['yaw_rmse']:.5f} (V1={v1_yaw:.5f}), "
              f"cte_rmse={best['cte_rmse']:.3f} (V1={v1_cte:.3f}), combined={best['combined']:.4f}")
        results[plat] = best

    coeffs = {
        "yaw_bias_by_platform": {p: results[p]["bias"] for p in PLATFORMS},
        "diagnostics": results,
        "v1_baseline": {p: r0["per_platform"][p] for p in PLATFORMS},
    }
    out_path = ROOT / "out" / "coeffs_debias.json"
    with out_path.open("w") as fh:
        json.dump(coeffs, fh, indent=2, default=float)
    print(f"\nwrote {out_path}")

    # Final pooled scoring with all biases applied.
    bias_by = {p: results[p]["bias"] for p in PLATFORMS}
    pf = make_predict_with_bias(bias_by)
    print("\nFinal pooled with all per-platform biases applied:")
    r_final = score(pf)
    print(f"  yaw_rmse: {r_final['yaw_rate_rmse']:.5f} (V1: {r0['yaw_rate_rmse']:.5f})")
    print(f"  cte_rmse: {r_final['cte_rmse']:.4f} (V1: {r0['cte_rmse']:.4f})")
    for p in PLATFORMS:
        m = r_final["per_platform"][p]
        v = r0["per_platform"][p]
        print(f"  {p}: yaw {v['yaw_rate_rmse']:.5f}->{m['yaw_rate_rmse']:.5f}, "
              f"cte {v['cte_rmse']:.3f}->{m['cte_rmse']:.3f}")


if __name__ == "__main__":
    main()
