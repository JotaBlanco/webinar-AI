"""Sweep Mach-E g and K_us near the recipe to reduce yaw bias / CTE drift."""
import sys, json, shutil
from pathlib import Path
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-06")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "out"))

from score import score
from predict_v1 import predict, PLATFORM_PARAMS_DEFAULT

paths = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))

base = {
    "FORD_F_150_LIGHTNING_MK1": {"g": 0.863, "L_eff": 3.26, "K_us": 0.00350, "tau": 0.060,
                                  "use_per_segment_delta0": False, "delta0": 0.00133},
    "FORD_MUSTANG_MACH_E_MK1": {"g": 0.891, "L_eff": 2.22, "K_us": 0.00150, "tau": 0.069,
                                 "use_per_segment_delta0": True, "delta0_fallback": -0.0001},
    "HYUNDAI_IONIQ_5": {"g": 0.938, "L_eff": 2.887, "K_us": 0.00289, "tau": 0.062,
                        "use_per_segment_delta0": True, "delta0_fallback": 0.0},
}

mache_paths = [p for p in paths if "MACH_E" in str(p)]
print(f"Mach-E segments: {len(mache_paths)}")

results = []
for g in [0.870, 0.880, 0.891, 0.900, 0.910, 0.920]:
    for K in [0.0010, 0.0015, 0.0020]:
        cfg = dict(base)
        cfg["FORD_MUSTANG_MACH_E_MK1"] = {**base["FORD_MUSTANG_MACH_E_MK1"], "g": g, "K_us": K}
        with open(ROOT / "out" / "coeffs.json", "w") as f:
            json.dump(cfg, f)
        res = score(predict, segment_paths=mache_paths, platform_filter="FORD_MUSTANG_MACH_E_MK1")
        pp = res["per_platform"]["FORD_MUSTANG_MACH_E_MK1"]
        results.append((g, K, pp["yaw_rate_rmse"], pp["yaw_residual_mean"],
                        pp["cte_rmse"], pp["cte_signed_mean"]))
        print(f"g={g:.3f} K={K:.4f} -> yaw_rmse={pp['yaw_rate_rmse']:.5f} bias={pp['yaw_residual_mean']:+.5f} cte={pp['cte_rmse']:.2f} drift={pp['cte_signed_mean']:+.2f}")
