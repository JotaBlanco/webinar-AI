"""Sigma sweep for M4 relaxation-length on dev split.

Per platform — find optimal sigma against yaw RMSE on dev. We hold V1 params,
only sigma moves.
"""
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

import pandas as pd  # noqa: E402


def make_predict(sigma_map: dict[str, float]):
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


def main():
    dev = dev_paths()
    platforms = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]
    sigmas = [0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0]

    # Per-platform sweep: score on platform-filtered dev to keep it cheap
    best = {}
    rows = []
    for plat in platforms:
        plat_dev = [p for p in dev if plat in str(p)]
        print(f"\n=== {plat} ({len(plat_dev)} segs) ===")
        best_s = None
        best_yaw = math.inf
        for s in sigmas:
            res = score(make_predict({plat: s}), segment_paths=plat_dev, platform_filter=plat)
            y = res["yaw_rate_rmse"]
            c = res["cte_rmse"]
            print(f"  sigma={s:>5}: yaw={y:.6f}, cte={c:.3f}")
            rows.append({"platform": plat, "sigma": s, "yaw": y, "cte": c})
            if y < best_yaw:
                best_yaw = y
                best_s = s
        best[plat] = {"sigma": best_s, "yaw": best_yaw}
        print(f"  best sigma={best_s}, yaw={best_yaw:.6f}")

    out = HERE / "m4_sigma_sweep.json"
    with out.open("w") as f:
        json.dump({"best": best, "rows": rows}, f, indent=2)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
