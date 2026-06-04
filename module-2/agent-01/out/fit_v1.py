"""Fit V1 per-platform on train segments, evaluate on dev, then score full set."""
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
from v1_model import predict_factory, PLATFORMS  # noqa: E402

import pandas as pd  # noqa: E402


def gather_by_platform():
    by_plat = {}
    for plat in PLATFORMS + ("TESLA_MODEL_3",):
        paths = sorted((ROOT / "data" / "sim" / "segments" / plat).glob("**/sim.csv"))
        by_plat[plat] = paths
    return by_plat


def route_grouped_split(paths, frac_dev=0.2, seed=42):
    """Split paths so all segments from a single route end up in same partition."""
    # Path layout: <plat>/<device>/<route>/<idx>/sim.csv  → parents[1] is route
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
    by_plat = gather_by_platform()

    train_segments = []
    dev_segments = []
    for plat in PLATFORMS:
        tr, dv = route_grouped_split(by_plat[plat], frac_dev=0.2)
        # Cap train size per platform to keep optimisation fast
        rng = random.Random(0)
        rng.shuffle(tr)
        tr = tr[:80]
        rng.shuffle(dv)
        dv = dv[:30]
        train_segments.extend(tr)
        dev_segments.extend(dv)
        print(f"{plat}: train={len(tr)}, dev={len(dv)}")

    # Initial coeffs and bounds per platform
    initial_coeffs = {
        "FORD_F_150_LIGHTNING_MK1": {"L_eff": 3.7,  "K_us": 0.0, "gain": 1.0, "bias": 0.0, "tau": 0.0},
        "FORD_MUSTANG_MACH_E_MK1":  {"L_eff": 2.98, "K_us": 0.0, "gain": 1.0, "bias": 0.0, "tau": 0.0},
        "HYUNDAI_IONIQ_5":          {"L_eff": 3.0,  "K_us": 0.0, "gain": 1.0, "bias": 0.0, "tau": 0.0},
    }
    bounds = {
        plat: {
            "L_eff": (1.5, 6.0),
            "K_us":  (-0.005, 0.02),
            "gain":  (0.5, 1.6),
            "bias":  (-0.02, 0.02),
            "tau":   (-0.3, 0.3),
        }
        for plat in PLATFORMS
    }

    print("\n== Fit V1 against yaw_plus_cte ==")
    res = fit(
        predict_factory,
        initial_coeffs,
        train_segments=train_segments,
        dev_segments=dev_segments,
        objective="yaw_plus_cte",
        bounds=bounds,
        cte_weight=2.0,
        max_iter=120,
        verbose=False,
    )
    print(format_fit_summary(res))

    # Persist coeffs
    out = {"coeffs": res["coeffs"]}
    (ROOT / "out" / "v1_coeffs.json").write_text(json.dumps(out, indent=2))
    print("\nWrote", ROOT / "out" / "v1_coeffs.json")

    # Score with fitted V1 over full set
    def predict_v1(sim_df, platform):
        coeffs = res["coeffs"].get(platform, {})
        cb = predict_factory(platform, coeffs)
        yr = cb(sim_df)
        return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)

    print("\n== Full scoring (V1) ==")
    seg_paths = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))
    full = score(predict_v1, segment_paths=seg_paths)
    print(format_summary(full))
    summary = {
        "yaw_rate_rmse": full["yaw_rate_rmse"],
        "cte_rmse": full["cte_rmse"],
        "per_platform": {p: {"yaw_rate_rmse": m["yaw_rate_rmse"],
                              "yaw_residual_mean": m["yaw_residual_mean"],
                              "cte_rmse": m["cte_rmse"],
                              "cte_signed_mean": m["cte_signed_mean"]}
                          for p, m in full["per_platform"].items()},
    }
    (ROOT / "out" / "v1_score.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
