"""Per-platform 1D sigma sweep on the M4 (relaxation length) model.

Grid search since there is only one parameter per platform. We score on
the frozen TRAIN split (to avoid optimising on dev) and verify on DEV.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
M4_DIR = ROOT / "phases/3-implement/models/m4-relaxation-length"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(M4_DIR))

from _shared.frozen_split import train_paths, dev_paths  # noqa: E402
from score import score  # noqa: E402
import model as m4  # noqa: E402


PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]


def make_predict(per_platform_sigma):
    def _predict(sim_df, platform):
        sigma = per_platform_sigma.get(platform)
        if sigma is None or platform == "TESLA_MODEL_3":
            import pandas as pd
            return sim_df[["yaw_rate_pred_rads"]].copy()
        fn = m4.predict_factory(platform, {"sigma": sigma})
        yr = fn(sim_df)
        out = sim_df[["yaw_rate_pred_rads"]].copy()
        out["yaw_rate_pred_rads"] = yr
        return out
    return _predict


def per_platform_yaw_rmse(predict_fn, paths, platform):
    plat_paths = [p for p in paths if p.parts[-5] == platform]
    r = score(predict_fn, segment_paths=plat_paths)
    return r["yaw_rate_rmse"], r.get("cte_rmse"), r["per_platform"].get(platform, {})


def main():
    train = train_paths()
    dev = dev_paths()
    print(f"train={len(train)}  dev={len(dev)}")

    # Coarse-to-fine 1D sweep per platform on the YAW metric using the train split.
    # Grid covers literature-typical band 0.1 - 2.5 m, finer near 0.5.
    grid = [0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.75, 0.9, 1.1, 1.4, 1.8, 2.2, 2.5]

    best = {}
    sweeps = {}
    for plat in PLATFORMS:
        plat_train = [p for p in train if p.parts[-5] == plat]
        print(f"\n[{plat}] {len(plat_train)} train segments")
        rows = []
        best_yaw = (float("inf"), None)
        best_cte = (float("inf"), None)
        for sigma in grid:
            def _pred(sim_df, platform, _s=sigma, _plat=plat):
                if platform != _plat:
                    return sim_df[["yaw_rate_pred_rads"]].copy()
                fn = m4.predict_factory(_plat, {"sigma": _s})
                yr = fn(sim_df)
                out = sim_df[["yaw_rate_pred_rads"]].copy()
                out["yaw_rate_pred_rads"] = yr
                return out
            r = score(_pred, segment_paths=plat_train)
            y = r["yaw_rate_rmse"]
            c = r["cte_rmse"]
            rows.append({"sigma": sigma, "yaw_rmse": y, "cte_rmse": c})
            if y < best_yaw[0]:
                best_yaw = (y, sigma)
            if c < best_cte[0]:
                best_cte = (c, sigma)
            print(f"  sigma={sigma:5.2f}  yaw {y:.6f}  cte {c:.4f}")
        best[plat] = {
            "sigma_best_yaw": best_yaw[1],
            "train_yaw_rmse": best_yaw[0],
            "sigma_best_cte": best_cte[1],
            "train_cte_rmse": best_cte[0],
        }
        sweeps[plat] = rows

    # Use yaw-best sigma per platform.
    chosen = {plat: best[plat]["sigma_best_yaw"] for plat in PLATFORMS}
    chosen_cte = {plat: best[plat]["sigma_best_cte"] for plat in PLATFORMS}

    predict_yaw = make_predict(chosen)
    predict_cte = make_predict(chosen_cte)
    print("\n=== DEV — sigma chosen by best-train-yaw ===")
    r_yaw_dev = score(predict_yaw, segment_paths=dev)
    print(f"  pooled yaw {r_yaw_dev['yaw_rate_rmse']:.6f}  cte {r_yaw_dev['cte_rmse']:.4f}")
    print("\n=== DEV — sigma chosen by best-train-cte ===")
    r_cte_dev = score(predict_cte, segment_paths=dev)
    print(f"  pooled yaw {r_cte_dev['yaw_rate_rmse']:.6f}  cte {r_cte_dev['cte_rmse']:.4f}")

    out = {
        "best_per_platform_yaw_objective": chosen,
        "best_per_platform_cte_objective": chosen_cte,
        "dev_yaw_objective": {
            "yaw_rate_rmse": r_yaw_dev["yaw_rate_rmse"],
            "cte_rmse": r_yaw_dev["cte_rmse"],
            "per_platform": {k: {kk: v[kk] for kk in ("yaw_rate_rmse", "cte_rmse", "n_segments") if kk in v} for k, v in r_yaw_dev["per_platform"].items()},
        },
        "dev_cte_objective": {
            "yaw_rate_rmse": r_cte_dev["yaw_rate_rmse"],
            "cte_rmse": r_cte_dev["cte_rmse"],
            "per_platform": {k: {kk: v[kk] for kk in ("yaw_rate_rmse", "cte_rmse", "n_segments") if kk in v} for k, v in r_cte_dev["per_platform"].items()},
        },
        "per_platform_best": best,
        "sweep_rows": sweeps,
    }
    out_path = HERE / "m4_sweep.json"
    with out_path.open("w") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
