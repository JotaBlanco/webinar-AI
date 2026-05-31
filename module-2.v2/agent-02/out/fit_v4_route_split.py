"""V4: same understeer model as V3, but fit on a route-grouped train split
and check generalisation on a dev split. Sanity check that the V3 numbers
aren't overfit.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-02")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
from score import score, format_summary  # noqa: E402

PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1",
             "HYUNDAI_IONIQ_5", "TESLA_MODEL_3"]
TRUTH_COL = {
    "FORD_F_150_LIGHTNING_MK1": "yaw_rate_meas_rads",
    "FORD_MUSTANG_MACH_E_MK1":  "yaw_rate_meas_rads",
    "HYUNDAI_IONIQ_5":          "yaw_rate_meas_rads",
    "TESLA_MODEL_3":            "psi_dot_rads",
}


def split_segments():
    train, dev = [], []
    rng = np.random.default_rng(42)
    for plat in PLATFORMS:
        segs = sorted((ROOT / "data" / "sim" / "segments" / plat).glob("**/sim.csv"))
        # Group by route (parents[1])
        routes = {}
        for p in segs:
            route = p.parents[1].name
            routes.setdefault(route, []).append(p)
        route_list = list(routes.keys())
        rng.shuffle(route_list)
        n_dev = max(1, int(0.2 * len(route_list)))
        dev_routes = set(route_list[:n_dev])
        for r, ps in routes.items():
            (dev if r in dev_routes else train).extend(ps)
    return train, dev


def collect_paths(paths, plat):
    xs, vs, ys = [], [], []
    for p in paths:
        if plat not in str(p):
            continue
        df = pd.read_csv(p, usecols=["v_mps", "yaw_rate_pred_rads", TRUTH_COL[plat]])
        mask = df["v_mps"].to_numpy() > 2.0
        if not mask.any():
            continue
        xs.append(df["yaw_rate_pred_rads"].to_numpy()[mask].astype(float))
        vs.append(df["v_mps"].to_numpy()[mask].astype(float))
        ys.append(df[TRUTH_COL[plat]].to_numpy()[mask].astype(float))
    if not xs:
        return None, None, None
    return np.concatenate(xs), np.concatenate(vs), np.concatenate(ys)


def fit_understeer(x, v, y):
    def res(p):
        k, K_us, b = p
        return (k * x) / (1.0 + K_us * v * v) + b - y
    out = least_squares(res, [1.0, 0.0, 0.0], method="trf")
    return out.x


def predict_factory(coeffs: dict):
    def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
        c = coeffs.get(platform, {"k": 1.0, "K_us": 0.0, "b": 0.0})
        v = sim_df["v_mps"].to_numpy(dtype=float)
        x = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        yp = (c["k"] * x) / (1.0 + c["K_us"] * v * v) + c["b"]
        out = pd.DataFrame(index=sim_df.index)
        out["yaw_rate_pred_rads"] = yp
        return out
    return predict


if __name__ == "__main__":
    train, dev = split_segments()
    print(f"split: train={len(train)} segs, dev={len(dev)} segs")
    coeffs = {}
    for plat in PLATFORMS:
        if plat == "TESLA_MODEL_3":
            coeffs[plat] = {"k": 1.0, "K_us": 0.0, "b": 0.0}
            continue
        x, v, y = collect_paths(train, plat)
        if x is None:
            coeffs[plat] = {"k": 1.0, "K_us": 0.0, "b": 0.0}
            continue
        k, K_us, b = fit_understeer(x, v, y)
        coeffs[plat] = {"k": float(k), "K_us": float(K_us), "b": float(b)}
        print(f"  {plat}: k={k:.5f}, K_us={K_us:+.5e}, b={b:+.5e}")

    print("\n=== TRAIN scoring ===")
    res_tr = score(predict_factory(coeffs), segment_paths=train)
    print(f"yaw={res_tr['yaw_rate_rmse']:.6f}, cte={res_tr['cte_rmse']:.4f}")
    print("\n=== DEV scoring ===")
    res_dv = score(predict_factory(coeffs), segment_paths=dev)
    print(f"yaw={res_dv['yaw_rate_rmse']:.6f}, cte={res_dv['cte_rmse']:.4f}")
    print("\n=== FULL scoring ===")
    segs = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))
    res_full = score(predict_factory(coeffs), segment_paths=segs)
    print(format_summary(res_full))
    (ROOT / "out" / "v4_coeffs.json").write_text(json.dumps(coeffs, indent=2))
