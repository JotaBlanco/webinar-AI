"""Fit V2 model (with cubic) and compare against V1."""
from __future__ import annotations
import json
import sys
import random
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-01")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "skills" / "fit-model"))
sys.path.insert(0, str(ROOT / "out"))

from score import score, format_summary  # noqa: E402
from fit import fit, format_fit_summary  # noqa: E402
from v2_model import predict_factory, PLATFORMS  # noqa: E402
import pandas as pd  # noqa: E402


def route_grouped_split(paths, frac_dev=0.2, seed=42):
    routes = {}
    for p in paths:
        route = p.resolve().parents[1].name
        routes.setdefault(route, []).append(p)
    keys = sorted(routes.keys())
    rng = random.Random(seed)
    rng.shuffle(keys)
    n_dev = max(1, int(len(keys) * frac_dev))
    dev_routes = set(keys[:n_dev])
    train, dev = [], []
    for r, ps in routes.items():
        (dev if r in dev_routes else train).extend(ps)
    return train, dev


def main():
    train_segments, dev_segments = [], []
    for plat in PLATFORMS:
        all_p = sorted((ROOT / "data" / "sim" / "segments" / plat).glob("**/sim.csv"))
        tr, dv = route_grouped_split(all_p, frac_dev=0.2)
        rng = random.Random(0); rng.shuffle(tr); rng.shuffle(dv)
        tr = tr[:120]; dv = dv[:40]
        train_segments.extend(tr); dev_segments.extend(dv)
        print(f"{plat}: train={len(tr)}, dev={len(dv)}")

    initial = {
        "FORD_F_150_LIGHTNING_MK1": {"L_eff": 3.71, "K_us": 0.0028, "gain": 0.95, "bias": -0.0055, "tau": -0.063, "c3": 0.0},
        "FORD_MUSTANG_MACH_E_MK1":  {"L_eff": 2.93, "K_us": 0.0030, "gain": 1.16, "bias": +0.0019, "tau": -0.054, "c3": 0.0},
        "HYUNDAI_IONIQ_5":          {"L_eff": 3.02, "K_us": 0.0037, "gain": 0.96, "bias": +0.0026, "tau": -0.029, "c3": 0.0},
    }
    bounds = {
        plat: {
            "L_eff": (1.5, 6.0),
            "K_us":  (-0.005, 0.025),
            "gain":  (0.5, 1.6),
            "bias":  (-0.02, 0.02),
            "tau":   (-0.3, 0.3),
            "c3":    (-5.0, 5.0),
        } for plat in PLATFORMS
    }

    res = fit(predict_factory, initial,
              train_segments=train_segments, dev_segments=dev_segments,
              objective="yaw_plus_cte", bounds=bounds, cte_weight=2.0,
              max_iter=200, verbose=False)
    print(format_fit_summary(res))

    def predict_v(sim_df, platform):
        coeffs = res["coeffs"].get(platform, {})
        cb = predict_factory(platform, coeffs)
        yr = cb(sim_df)
        return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)

    seg_paths = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))
    full = score(predict_v, segment_paths=seg_paths)
    print(format_summary(full, top_n=3))

    (ROOT / "out" / "v3_coeffs.json").write_text(json.dumps({"coeffs": res["coeffs"]}, indent=2))
    (ROOT / "out" / "v3_score.json").write_text(json.dumps({
        "yaw_rate_rmse": full["yaw_rate_rmse"],
        "cte_rmse":      full["cte_rmse"],
        "per_platform":  {p: {"yaw_rate_rmse": m["yaw_rate_rmse"],
                               "yaw_residual_mean": m["yaw_residual_mean"],
                               "cte_rmse": m["cte_rmse"],
                               "cte_signed_mean": m["cte_signed_mean"]}
                          for p, m in full["per_platform"].items()},
    }, indent=2))


if __name__ == "__main__":
    main()
