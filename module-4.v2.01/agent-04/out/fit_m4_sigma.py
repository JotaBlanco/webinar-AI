"""Fit M4 (relaxation-length) sigma per platform via 1D grid search.

Single parameter per platform. Uses train split, evaluates on dev.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
TPL = HERE.parent
sys.path.insert(0, str(TPL))
sys.path.insert(0, str(TPL / "skills" / "score-model"))
sys.path.insert(0, str(TPL / "phases" / "3-implement" / "models" / "m4-relaxation-length"))

from _shared.frozen_split import train_paths, dev_paths
from score import score
from model import predict_factory

PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]

SIGMAS = [0.0, 0.1, 0.2, 0.3, 0.5, 0.8, 1.2, 1.8, 2.5, 3.5, 5.0]

train = train_paths()
dev = dev_paths()

print(f"train={len(train)} dev={len(dev)} sigmas={SIGMAS}")

# For each sigma try the same sigma on all platforms, compute per-platform yaw rmse.
best = {}
results = {p: [] for p in PLATFORMS}

for sigma in SIGMAS:
    coeffs = {p: {"sigma": sigma} for p in PLATFORMS}
    coeffs["TESLA_MODEL_3"] = {}

    def predict_fn(sim_df, platform):
        c = coeffs.get(platform, {})
        yr = predict_factory(platform, c)(sim_df)
        out = sim_df[["yaw_rate_pred_rads"]].copy()
        out["yaw_rate_pred_rads"] = yr
        return out

    result = score(predict_fn, segment_paths=train)
    pp = result["per_platform"]
    line = [f"sigma={sigma:.2f}"]
    for plat in PLATFORMS:
        rmse = pp[plat]["yaw_rate_rmse"]
        cte = pp[plat]["cte_rmse"]
        line.append(f"{plat[:8]}={rmse:.5f}/{cte:.1f}")
        results[plat].append((sigma, rmse, cte))
    print(" | ".join(line))

# Best per platform
print("\nbest by yaw rmse (train):")
final_coeffs = {}
for plat in PLATFORMS:
    rs = results[plat]
    rs.sort(key=lambda x: x[1])
    s_best, yaw_b, cte_b = rs[0]
    print(f"  {plat}: sigma={s_best}, yaw={yaw_b:.5f}, cte={cte_b:.2f}")
    final_coeffs[plat] = {"sigma": float(s_best)}

with (HERE / "m4_coeffs.json").open("w") as f:
    json.dump(final_coeffs, f, indent=2)
print(f"wrote {HERE/'m4_coeffs.json'}")

# Now eval on dev
coeffs = final_coeffs.copy()

def predict_fn(sim_df, platform):
    c = coeffs.get(platform, {})
    yr = predict_factory(platform, c)(sim_df)
    out = sim_df[["yaw_rate_pred_rads"]].copy()
    out["yaw_rate_pred_rads"] = yr
    return out

dev_result = score(predict_fn, segment_paths=dev)
print(f"\nDEV pooled: yaw={dev_result['yaw_rate_rmse']:.6f} cte={dev_result['cte_rmse']:.2f}")
with (HERE / "m4_scorecard_dev.json").open("w") as f:
    json.dump({
        "yaw_rate_rmse": dev_result["yaw_rate_rmse"],
        "cte_rmse": dev_result["cte_rmse"],
        "per_platform": {p: {"yaw_rate_rmse": s["yaw_rate_rmse"], "cte_rmse": s["cte_rmse"], "yaw_residual_mean": s.get("yaw_residual_mean")} for p, s in dev_result["per_platform"].items()},
        "coeffs": final_coeffs,
    }, f, indent=2, default=str)
