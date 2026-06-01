"""V4: V3 + cubic delta term to handle tire-slip saturation.

V4: yr = v * (delta - delta_off - c3 * delta^3) / (L + K_us * v^2)
        + tau * d(delta)/dt + bias
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

from score import score, format_summary
from fit import fit, format_fit_summary

WHEELBASE = {
    "TESLA_MODEL_3":            2.875,
    "FORD_MUSTANG_MACH_E_MK1":  2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "HYUNDAI_IONIQ_5":          3.00,
}


def make_v4_predict(platform, coeffs):
    L = WHEELBASE[platform]
    Kus = coeffs.get("K_us", 0.0)
    tau = coeffs.get("tau", 0.0)
    bias = coeffs.get("bias", 0.0)
    delta_off = coeffs.get("delta_off", 0.0)
    c3 = coeffs.get("c3", 0.0)
    def predict(sim_df):
        t = sim_df["t_s"].to_numpy(dtype=float)
        v = sim_df["v_mps"].to_numpy(dtype=float)
        delta = sim_df["delta_road_rad"].to_numpy(dtype=float) - delta_off
        d_eff = delta - c3 * delta**3
        denom = L + Kus * v * v
        ddelta_dt = np.gradient(delta, t)
        return v * d_eff / denom + tau * ddelta_dt + bias
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
    platforms = list(WHEELBASE.keys())
    init = {p: {"K_us": 0.003, "bias": 0.0, "tau": -0.05,
                "delta_off": 0.0, "c3": 0.0} for p in platforms}
    init["TESLA_MODEL_3"] = {k: 0.0 for k in init["TESLA_MODEL_3"]}
    bounds = {p: {"K_us": (-0.005, 0.02), "bias": (-0.02, 0.02),
                  "tau": (-0.3, 0.3), "delta_off": (-0.02, 0.02),
                  "c3": (-30.0, 30.0)} for p in platforms}

    for obj, cw in [("yaw_plus_cte", 1.0), ("yaw_plus_cte", 2.0), ("yaw", None)]:
        kwargs = dict(predict_factory=make_v4_predict, initial_coeffs=init,
                      train_segments=train, dev_segments=dev,
                      objective=obj, bounds=bounds, method="L-BFGS-B",
                      max_iter=200, verbose=False)
        if cw is not None:
            kwargs["cte_weight"] = cw
        print(f"\n=== V4 fit: {obj} cw={cw} ===")
        res = fit(**kwargs)
        print(format_fit_summary(res))
        def predict_full(sim_df, platform):
            yr = make_v4_predict(platform, res["coeffs"].get(platform, {}))(sim_df)
            return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
        r = score(predict_full)
        print(f"FULL: yaw_rmse={r['yaw_rate_rmse']:.6f}  cte_rmse={r['cte_rmse']:.4f}")
        tag = f"v4_{obj}_cw{cw}"
        (ROOT / "out" / f"{tag}_coeffs.json").write_text(
            json.dumps({"coeffs": res["coeffs"], "yaw": r["yaw_rate_rmse"], "cte": r["cte_rmse"]},
                       indent=2, default=str))


if __name__ == "__main__":
    main()
