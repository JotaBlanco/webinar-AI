"""V3: V2 + try cte-heavy fit and a steering offset term.

V3: yr = v * (delta_road - delta_off) / (L + K_us * v^2) + tau * d(delta)/dt + bias
"""
import os, sys, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-03")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "skills" / "fit-model"))
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "code"))

from score import score, format_summary
from fit import fit, format_fit_summary

WHEELBASE = {
    "TESLA_MODEL_3":            2.875,
    "FORD_MUSTANG_MACH_E_MK1":  2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "HYUNDAI_IONIQ_5":          3.00,
}


def make_v3_predict(platform, coeffs):
    L = WHEELBASE[platform]
    Kus = coeffs.get("K_us", 0.0)
    tau = coeffs.get("tau", 0.0)
    bias = coeffs.get("bias", 0.0)
    delta_off = coeffs.get("delta_off", 0.0)
    def predict(sim_df):
        t = sim_df["t_s"].to_numpy(dtype=float)
        v = sim_df["v_mps"].to_numpy(dtype=float)
        delta = sim_df["delta_road_rad"].to_numpy(dtype=float) - delta_off
        denom = L + Kus * v * v
        ddelta_dt = np.gradient(delta, t)
        yr = v * delta / denom + tau * ddelta_dt + bias
        return yr
    return predict


def collect_segments():
    seg_root = ROOT / "data" / "sim" / "segments"
    return sorted(p for p in seg_root.glob("*/**/sim.csv") if p.is_file())


def split_train_dev(segments, dev_frac=0.2, seed=42):
    rng = np.random.default_rng(seed)
    by_plat_route = {}
    for p in segments:
        plat = p.resolve().parents[3].name
        route = p.resolve().parents[1].name
        by_plat_route.setdefault(plat, {}).setdefault(route, []).append(p)
    train, dev = [], []
    for plat, routes in by_plat_route.items():
        route_list = list(routes.keys())
        rng.shuffle(route_list)
        n_dev = max(1, int(len(route_list) * dev_frac))
        dev_routes = set(route_list[:n_dev])
        for r, files in routes.items():
            (dev if r in dev_routes else train).extend(files)
    return train, dev


def main():
    segments = collect_segments()
    train, dev = split_train_dev(segments)
    print(f"Train: {len(train)}  Dev: {len(dev)}")

    platforms = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5", "TESLA_MODEL_3"]
    init = {p: {"K_us": 0.003, "bias": 0.0, "tau": -0.05, "delta_off": 0.0} for p in platforms}
    init["TESLA_MODEL_3"] = {"K_us": 0.0, "bias": 0.0, "tau": 0.0, "delta_off": 0.0}
    bounds = {p: {"K_us": (-0.005, 0.02), "bias": (-0.02, 0.02),
                  "tau": (-0.3, 0.3), "delta_off": (-0.02, 0.02)} for p in platforms}

    # 1) yaw-only fit
    print("\n=== V3 fit: yaw ===")
    res_y = fit(predict_factory=make_v3_predict, initial_coeffs=init,
                train_segments=train, dev_segments=dev,
                objective="yaw", bounds=bounds, method="L-BFGS-B",
                max_iter=200, verbose=False)
    print(format_fit_summary(res_y))

    # 2) yaw_plus_cte fit with heavy CTE weight
    print("\n=== V3 fit: yaw_plus_cte heavy CTE ===")
    res_yc = fit(predict_factory=make_v3_predict, initial_coeffs=init,
                 train_segments=train, dev_segments=dev,
                 objective="yaw_plus_cte", bounds=bounds, method="L-BFGS-B",
                 max_iter=200, cte_weight=2.0, verbose=False)
    print(format_fit_summary(res_yc))

    # Score both on full data
    def make_full(coeffs_all):
        def predict_full(sim_df, platform):
            c = coeffs_all.get(platform, {})
            yr = make_v3_predict(platform, c)(sim_df)
            return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
        return predict_full

    print("\n=== Score V3-yaw ===")
    ry = score(make_full(res_y["coeffs"]))
    print(f"yaw_rmse={ry['yaw_rate_rmse']:.6f}  cte_rmse={ry['cte_rmse']:.4f}")
    print("\n=== Score V3-yaw+cte ===")
    ryc = score(make_full(res_yc["coeffs"]))
    print(f"yaw_rmse={ryc['yaw_rate_rmse']:.6f}  cte_rmse={ryc['cte_rmse']:.4f}")

    out = {
        "v3_yaw": {"coeffs": res_y["coeffs"], "yaw": ry["yaw_rate_rmse"], "cte": ry["cte_rmse"]},
        "v3_yaw_cte": {"coeffs": res_yc["coeffs"], "yaw": ryc["yaw_rate_rmse"], "cte": ryc["cte_rmse"]},
    }
    (ROOT / "out" / "fit_v3_results.json").write_text(json.dumps(out, indent=2, default=str))
    print("Saved fit_v3_results.json")


if __name__ == "__main__":
    main()
