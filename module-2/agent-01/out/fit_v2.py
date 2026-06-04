"""V2 — refit with CTE-heavier objective and slightly wider tau, then score."""
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
        rng = random.Random(0)
        rng.shuffle(tr); rng.shuffle(dv)
        # Larger training samples (more long segments) helps CTE signal
        tr = tr[:120]; dv = dv[:40]
        train_segments.extend(tr); dev_segments.extend(dv)
        print(f"{plat}: train={len(tr)}, dev={len(dv)}")

    initial_coeffs = {
        "FORD_F_150_LIGHTNING_MK1": {"L_eff": 3.7,  "K_us": 0.003, "gain": 0.95, "bias": 0.0, "tau": -0.06},
        "FORD_MUSTANG_MACH_E_MK1":  {"L_eff": 2.98, "K_us": 0.003, "gain": 1.15, "bias": 0.0, "tau": -0.05},
        "HYUNDAI_IONIQ_5":          {"L_eff": 3.0,  "K_us": 0.004, "gain": 0.96, "bias": 0.0, "tau": -0.03},
    }
    bounds = {
        plat: {
            "L_eff": (1.5, 6.0),
            "K_us":  (-0.005, 0.025),
            "gain":  (0.5, 1.6),
            "bias":  (-0.02, 0.02),
            "tau":   (-0.5, 0.5),
        }
        for plat in PLATFORMS
    }

    print("\n== V2 fit: pure CTE objective ==")
    res_cte = fit(
        predict_factory, initial_coeffs,
        train_segments=train_segments, dev_segments=dev_segments,
        objective="cte", bounds=bounds, max_iter=150, verbose=False,
    )
    print(format_fit_summary(res_cte))

    print("\n== V2 fit: yaw_plus_cte cte_weight=4 ==")
    res_bl = fit(
        predict_factory, initial_coeffs,
        train_segments=train_segments, dev_segments=dev_segments,
        objective="yaw_plus_cte", bounds=bounds, cte_weight=4.0,
        max_iter=150, verbose=False,
    )
    print(format_fit_summary(res_bl))

    # Score both
    def make_predict(coeffs_map):
        def predict_fn(sim_df, platform):
            coeffs = coeffs_map.get(platform, {})
            cb = predict_factory(platform, coeffs)
            yr = cb(sim_df)
            return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
        return predict_fn

    seg_paths = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))

    print("\n== Full scoring: V2 CTE-only fit ==")
    full_cte = score(make_predict(res_cte["coeffs"]), segment_paths=seg_paths)
    print(format_summary(full_cte, top_n=3))

    print("\n== Full scoring: V2 blend fit ==")
    full_bl = score(make_predict(res_bl["coeffs"]), segment_paths=seg_paths)
    print(format_summary(full_bl, top_n=3))

    # Persist whichever is better on CTE (primary "drift killer")
    if full_cte["cte_rmse"] < full_bl["cte_rmse"]:
        best = ("cte", res_cte, full_cte)
    else:
        best = ("yaw_plus_cte", res_bl, full_bl)
    print(f"\nBest by CTE: {best[0]}  yaw={best[2]['yaw_rate_rmse']:.5f}  cte={best[2]['cte_rmse']:.3f}")

    (ROOT / "out" / "v2_coeffs.json").write_text(json.dumps({"coeffs": best[1]["coeffs"], "objective": best[0]}, indent=2))


if __name__ == "__main__":
    main()
