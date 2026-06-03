"""Finer sigma sweep for M4 — narrow in on the 0.2-0.4 zone per platform."""
from __future__ import annotations
import json
import sys
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
TPL = HERE.parent
M4 = TPL / "phases" / "3-implement" / "models" / "m4-relaxation-length"

sys.path.insert(0, str(TPL))
sys.path.insert(0, str(TPL / "skills" / "score-model"))
sys.path.insert(0, str(M4))

from _shared.frozen_split import dev_paths  # noqa: E402
from score import score  # noqa: E402
from model import predict_factory  # noqa: E402


def make_predict(sigma_map):
    factories = {p: predict_factory(p, {"sigma": s}) for p, s in sigma_map.items()}
    def _p(sim_df, platform):
        if platform in factories:
            yr = factories[platform](sim_df)
        else:
            yr = sim_df["yaw_rate_pred_rads"].to_numpy()
        out = sim_df[["yaw_rate_pred_rads"]].copy()
        out["yaw_rate_pred_rads"] = yr
        return out
    return _p


dev = dev_paths()
platforms = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]
sigmas = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40]

best = {}
for plat in platforms:
    plat_dev = [p for p in dev if plat in str(p)]
    print(f"\n=== {plat} ({len(plat_dev)} segs) ===")
    best_s = None
    best_yaw = math.inf
    best_cte = None
    for s in sigmas:
        res = score(make_predict({plat: s}), segment_paths=plat_dev, platform_filter=plat)
        y = res["yaw_rate_rmse"]
        c = res["cte_rmse"]
        print(f"  sigma={s:>5}: yaw={y:.6f}, cte={c:.3f}")
        if y < best_yaw:
            best_yaw = y
            best_s = s
            best_cte = c
    best[plat] = {"sigma": best_s, "yaw": best_yaw, "cte": best_cte}
    print(f"  best sigma={best_s}, yaw={best_yaw:.6f}, cte={best_cte:.3f}")

print("\nBest per-platform:")
for p, v in best.items():
    print(f"  {p}: sigma={v['sigma']}, yaw={v['yaw']:.6f}")

with (HERE / "m4_fine_sweep.json").open("w") as f:
    json.dump(best, f, indent=2)
