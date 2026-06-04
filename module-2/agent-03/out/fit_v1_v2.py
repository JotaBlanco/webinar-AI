"""Fit V1 (understeer) and V2 (understeer + steering-rate lead) per platform.

V1: yr = v * delta_road / (L + K_us * v^2) + bias
V2: yr = v * delta_road / (L + K_us * v^2) + tau * d(delta_road)/dt + bias

We fit K_us (understeer gradient s²/m), tau (s), bias (rad/s) per platform.
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
from fit import fit, format_fit_summary  # may exist; will try except
from parameters import PARAM_BY_PLATFORM

# Wheelbase from PARAM_BY_PLATFORM (also fallback for hyundai)
WHEELBASE = {
    "TESLA_MODEL_3":            2.875,
    "FORD_MUSTANG_MACH_E_MK1":  2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "HYUNDAI_IONIQ_5":          3.00,  # approx, will lean on K_us fit anyway
}


def _delta_dot(t, delta):
    return np.gradient(delta, t)


def make_v1_predict(platform, coeffs):
    L = WHEELBASE[platform]
    Kus = coeffs.get("K_us", 0.0)
    bias = coeffs.get("bias", 0.0)
    def predict(sim_df):
        v = sim_df["v_mps"].to_numpy(dtype=float)
        delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
        denom = L + Kus * v * v
        yr = v * delta / denom + bias
        return yr
    return predict


def make_v2_predict(platform, coeffs):
    L = WHEELBASE[platform]
    Kus = coeffs.get("K_us", 0.0)
    tau = coeffs.get("tau", 0.0)
    bias = coeffs.get("bias", 0.0)
    def predict(sim_df):
        t = sim_df["t_s"].to_numpy(dtype=float)
        v = sim_df["v_mps"].to_numpy(dtype=float)
        delta = sim_df["delta_road_rad"].to_numpy(dtype=float)
        denom = L + Kus * v * v
        ddelta_dt = _delta_dot(t, delta)
        yr = v * delta / denom + tau * ddelta_dt + bias
        return yr
    return predict


def collect_segments():
    seg_root = ROOT / "data" / "sim" / "segments"
    segs = sorted(p for p in seg_root.glob("*/**/sim.csv") if p.is_file())
    return segs


def split_train_dev(segments, dev_frac=0.2, seed=42):
    # Route-grouped split per platform.
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
            if r in dev_routes:
                dev.extend(files)
            else:
                train.extend(files)
    return train, dev


def main():
    segments = collect_segments()
    print(f"Total segments: {len(segments)}")
    train, dev = split_train_dev(segments)
    print(f"Train segments: {len(train)}, dev segments: {len(dev)}")

    platforms = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]
    # Tesla skip - its truth IS V0

    # ---- V1 fit ----
    init_v1 = {p: {"K_us": 0.001, "bias": 0.0} for p in platforms}
    # Tesla: include but with zero so it passes through V0
    init_v1["TESLA_MODEL_3"] = {"K_us": 0.0, "bias": 0.0}

    bounds_v1 = {p: {"K_us": (-0.01, 0.05), "bias": (-0.02, 0.02)} for p in platforms}
    bounds_v1["TESLA_MODEL_3"] = {"K_us": (-0.01, 0.05), "bias": (-0.02, 0.02)}

    print("\n=== Fitting V1 (yaw+cte) ===")
    res_v1 = fit(
        predict_factory=make_v1_predict,
        initial_coeffs=init_v1,
        train_segments=train,
        dev_segments=dev,
        objective="yaw_plus_cte",
        bounds=bounds_v1,
        method="L-BFGS-B",
        max_iter=100,
        cte_weight=1.0,
        verbose=False,
    )
    print(format_fit_summary(res_v1))
    print("V1 coeffs:", json.dumps(res_v1["coeffs"], indent=2))

    # ---- V2 fit ----
    init_v2 = {}
    for p in platforms:
        c = dict(res_v1["coeffs"][p])
        c["tau"] = 0.1
        init_v2[p] = c
    init_v2["TESLA_MODEL_3"] = dict(res_v1["coeffs"]["TESLA_MODEL_3"]); init_v2["TESLA_MODEL_3"]["tau"] = 0.0

    bounds_v2 = {p: {"K_us": (-0.01, 0.05), "bias": (-0.02, 0.02), "tau": (-0.5, 0.5)} for p in init_v2}

    print("\n=== Fitting V2 (yaw+cte) ===")
    res_v2 = fit(
        predict_factory=make_v2_predict,
        initial_coeffs=init_v2,
        train_segments=train,
        dev_segments=dev,
        objective="yaw_plus_cte",
        bounds=bounds_v2,
        method="L-BFGS-B",
        max_iter=200,
        cte_weight=1.0,
        verbose=False,
    )
    print(format_fit_summary(res_v2))
    print("V2 coeffs:", json.dumps(res_v2["coeffs"], indent=2))

    # ---- Score V1 and V2 on FULL data ----
    def predict_v1_full(sim_df, platform):
        coeffs = res_v1["coeffs"].get(platform, {"K_us": 0.0, "bias": 0.0})
        yr = make_v1_predict(platform, coeffs)(sim_df)
        return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)

    def predict_v2_full(sim_df, platform):
        coeffs = res_v2["coeffs"].get(platform, {"K_us": 0.0, "bias": 0.0, "tau": 0.0})
        yr = make_v2_predict(platform, coeffs)(sim_df)
        return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)

    print("\n=== Score V1 (all data) ===")
    rv1 = score(predict_v1_full)
    print(format_summary(rv1, top_n=3))
    print("V1 HEADLINE: yaw=", rv1["yaw_rate_rmse"], "cte=", rv1["cte_rmse"])

    print("\n=== Score V2 (all data) ===")
    rv2 = score(predict_v2_full)
    print(format_summary(rv2, top_n=3))
    print("V2 HEADLINE: yaw=", rv2["yaw_rate_rmse"], "cte=", rv2["cte_rmse"])

    # Persist coeffs
    out = {"v1": res_v1["coeffs"], "v2": res_v2["coeffs"],
           "v1_score": {"yaw": rv1["yaw_rate_rmse"], "cte": rv1["cte_rmse"]},
           "v2_score": {"yaw": rv2["yaw_rate_rmse"], "cte": rv2["cte_rmse"]}}
    (ROOT / "out" / "fit_results.json").write_text(json.dumps(out, indent=2, default=str))
    print("\nSaved fit_results.json")


if __name__ == "__main__":
    main()
