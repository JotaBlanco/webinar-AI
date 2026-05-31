"""Fit per-platform coefficients for an understeer-corrected bicycle yaw predictor.

Model:
    yaw_pred = v * delta_road / (L_eff + K_us * v^2) + bias_static + bias_steer * delta_road

V0 is psi_dot = (v / L) * tan(delta_road). We use small-angle delta plus a
v^2-coupled understeer denominator (classic bicycle steady-state form).
We deliberately drop `gain` because it's degenerate with 1/L_eff at low speed.

Per-platform parameters:
    L_eff      : effective wheelbase term (m)
    K_us       : understeer coefficient (s^2/m)
    bias_static: constant yaw offset (rad/s) — sensor offset
    bias_steer : steer-coupled offset (rad/s per rad of road wheel)

Tesla is left as V0 passthrough (its 'truth' IS V0; fitting moves the score away from 0).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "skills" / "fit-model"))
sys.path.insert(0, str(ROOT / "_shared"))

from score import score, format_summary  # noqa: E402
from fit import fit, format_fit_summary  # noqa: E402


INIT = {
    "FORD_F_150_LIGHTNING_MK1": {"L_eff": 3.70, "K_us": 0.0030, "bias_static": 0.0, "bias_steer": 0.0},
    "FORD_MUSTANG_MACH_E_MK1":  {"L_eff": 2.984,"K_us": 0.0020, "bias_static": 0.0, "bias_steer": 0.0},
    "HYUNDAI_IONIQ_5":          {"L_eff": 3.00, "K_us": 0.0050, "bias_static": 0.0, "bias_steer": 0.0},
    "TESLA_MODEL_3":            {"_noop": 0.0},
}

BOUNDS = {
    "FORD_F_150_LIGHTNING_MK1": {"L_eff": (2.0, 6.0), "K_us": (-0.005, 0.030), "bias_static": (-0.01, 0.01), "bias_steer": (-0.3, 0.3)},
    "FORD_MUSTANG_MACH_E_MK1":  {"L_eff": (1.5, 5.0), "K_us": (-0.005, 0.030), "bias_static": (-0.01, 0.01), "bias_steer": (-0.3, 0.3)},
    "HYUNDAI_IONIQ_5":          {"L_eff": (1.5, 5.0), "K_us": (-0.005, 0.030), "bias_static": (-0.01, 0.01), "bias_steer": (-0.3, 0.3)},
    "TESLA_MODEL_3":            {"_noop": (-1.0, 1.0)},
}


def predict_factory(platform: str, coeffs: dict):
    if platform == "TESLA_MODEL_3":
        def cb_tesla(sim_df: pd.DataFrame) -> np.ndarray:
            return sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        return cb_tesla

    L_eff = float(coeffs["L_eff"])
    K_us  = float(coeffs["K_us"])
    bs    = float(coeffs["bias_static"])
    bd    = float(coeffs["bias_steer"])

    def cb(sim_df: pd.DataFrame) -> np.ndarray:
        v = sim_df["v_mps"].to_numpy(dtype=float)
        d = sim_df["delta_road_rad"].to_numpy(dtype=float)
        denom = L_eff + K_us * v * v
        # Guard against tiny/negative denom — clamp magnitude.
        denom = np.where(denom < 0.1, 0.1, denom)
        yr = v * d / denom + bs + bd * d
        return yr
    return cb


def all_segments():
    return sorted(Path(ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))


def make_train_dev(paths, dev_frac=0.15, seed=0):
    rng = np.random.default_rng(seed)
    by_route = {}
    for p in paths:
        route = p.resolve().parents[1].name
        by_route.setdefault(route, []).append(p)
    routes = sorted(by_route.keys())
    rng.shuffle(routes)
    n_dev = max(1, int(len(routes) * dev_frac))
    dev_routes = set(routes[:n_dev])
    train = [p for r, ps in by_route.items() if r not in dev_routes for p in ps]
    dev   = [p for r, ps in by_route.items() if r in dev_routes for p in ps]
    return train, dev


def main():
    paths = all_segments()
    print(f"total segments: {len(paths)}")
    train, dev = make_train_dev(paths, dev_frac=0.15)
    print(f"train: {len(train)} segs, dev: {len(dev)} segs")

    # Pass 1: L-BFGS-B from physically-motivated init (handles Mach-E and Hyundai well).
    result = fit(
        predict_factory,
        initial_coeffs=INIT,
        train_segments=train,
        dev_segments=dev,
        objective="yaw_plus_cte",
        bounds=BOUNDS,
        method="L-BFGS-B",
        max_iter=200,
        cte_weight=1.0,
        verbose=False,
    )
    print("=== L-BFGS-B pass 1 ===")
    print(format_fit_summary(result))

    # Pass 2: if any platform looks unconverged (train_obj still high or close to init),
    # restart with Nelder-Mead from a perturbed init.
    coeffs1 = result["coeffs"]

    # Identify platforms still close to initial (un-moved L-BFGS-B). Heuristic:
    # check if L_eff changed by less than 1% from init.
    needs_rescue = []
    for plat, init in INIT.items():
        if plat == "TESLA_MODEL_3":
            continue
        c1 = coeffs1.get(plat, init)
        if abs(c1["L_eff"] - init["L_eff"]) / init["L_eff"] < 0.005 \
           and abs(c1["K_us"] - init["K_us"]) < 1e-5 \
           and abs(c1["bias_static"]) < 1e-6:
            needs_rescue.append(plat)
    if needs_rescue:
        print(f"\nPlatforms needing rescue (L-BFGS-B stuck): {needs_rescue}")
        rescue_init = {plat: dict(INIT[plat]) for plat in needs_rescue}
        # Perturb to escape flat patch.
        for plat, c in rescue_init.items():
            c["L_eff"]  = c["L_eff"] * 1.05
            c["K_us"]   = c["K_us"]  + 0.001
            c["bias_static"] = 0.0005
        nm = fit(
            predict_factory,
            initial_coeffs=rescue_init,
            train_segments=train,
            dev_segments=None,
            objective="yaw_plus_cte",
            bounds={k: BOUNDS[k] for k in needs_rescue},
            method="Nelder-Mead",
            max_iter=400,
            cte_weight=1.0,
            verbose=False,
        )
        print("Rescue NM:")
        print(format_fit_summary(nm))
        # Polish with bounded L-BFGS-B again.
        rescue_polish = fit(
            predict_factory,
            initial_coeffs=nm["coeffs"],
            train_segments=train,
            dev_segments=dev,
            objective="yaw_plus_cte",
            bounds={k: BOUNDS[k] for k in needs_rescue},
            method="L-BFGS-B",
            max_iter=200,
            cte_weight=1.0,
            verbose=False,
        )
        print("Rescue polish:")
        print(format_fit_summary(rescue_polish))
        for plat in needs_rescue:
            coeffs1[plat] = rescue_polish["coeffs"][plat]

    # Persist coefficients.
    out_path = ROOT / "final-model" / "coeffs.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(coeffs1, indent=2, sort_keys=True))
    print(f"\nWrote {out_path}")
    print("Final coeffs:", json.dumps(coeffs1, indent=2))

    # Full-data score.
    def my_predict(sim_df, platform):
        cb = predict_factory(platform, coeffs1.get(platform, INIT[platform]))
        out = pd.DataFrame(index=sim_df.index)
        out["yaw_rate_pred_rads"] = cb(sim_df)
        return out

    r = score(my_predict)
    print("\n=== FINAL SCORE ===")
    print(format_summary(r))


if __name__ == "__main__":
    main()
