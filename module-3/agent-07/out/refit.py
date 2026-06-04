"""Refit per-platform coefficients with scipy via fit-model skill.

Model shape: KS + understeer + lag + per-segment delta0 (gated per platform).
Objective: yaw_plus_cte.
"""
import sys
import json
from pathlib import Path
import random

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-07")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "skills" / "fit-model"))

from score import score, format_summary  # noqa
from fit import fit, format_fit_summary  # noqa


def _per_segment_delta0(sim_df, fallback=0.0, yr_thresh=0.03, v_thresh=5.0, min_rows=50):
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < yr_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def make_predict(platform, coeffs, use_per_segment_delta0):
    g = coeffs["g"]
    L_eff = coeffs["L_eff"]
    K_us = coeffs["K_us"]
    tau = coeffs["tau"]
    delta0_fb = coeffs["delta0"]

    def predict_arr(sim_df):
        if use_per_segment_delta0:
            delta0 = _per_segment_delta0(sim_df, fallback=delta0_fb)
        else:
            delta0 = delta0_fb
        delta = (sim_df["delta_road_rad"].to_numpy() - delta0) * g
        v = sim_df["v_mps"].to_numpy()
        denom = L_eff + K_us * v * v
        # Guard against negative L_eff during optimisation.
        denom = np.where(denom <= 0.1, 0.1, denom)
        yr_ss = v * delta / denom
        t = sim_df["t_s"].to_numpy()
        dt = np.diff(t, prepend=t[0])
        tau_loc = max(tau, 1e-3)
        alpha = dt / (tau_loc + dt)
        yr = np.empty_like(yr_ss)
        yr[0] = yr_ss[0]
        for i in range(1, len(yr)):
            yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
        return yr
    return predict_arr


PLATFORM_GATES = {
    "FORD_F_150_LIGHTNING_MK1": False,
    "FORD_MUSTANG_MACH_E_MK1": True,
    "HYUNDAI_IONIQ_5": True,
}

INITIAL = {
    "FORD_F_150_LIGHTNING_MK1": {"g": 0.863, "L_eff": 3.26, "K_us": 0.00350, "tau": 0.060, "delta0": 0.00133},
    "FORD_MUSTANG_MACH_E_MK1":  {"g": 0.891, "L_eff": 2.22, "K_us": 0.00150, "tau": 0.069, "delta0": -0.0001},
    "HYUNDAI_IONIQ_5":          {"g": 0.938, "L_eff": 2.887, "K_us": 0.00289, "tau": 0.062, "delta0": 0.0},
}

BOUNDS = {
    plat: {"g": (0.5, 1.5), "L_eff": (1.5, 4.5), "K_us": (-0.005, 0.02), "tau": (0.005, 0.3), "delta0": (-0.05, 0.05)}
    for plat in INITIAL
}


def predict_factory(platform, coeffs):
    gated = PLATFORM_GATES[platform]
    return make_predict(platform, coeffs, gated)


# Route-grouped train/dev split per platform — 80/20.
def route_split(segs, seed=7):
    by_route = {}
    for p in segs:
        route = p.resolve().parents[1].name
        by_route.setdefault(route, []).append(p)
    routes = sorted(by_route.keys())
    rng = random.Random(seed)
    rng.shuffle(routes)
    cut = int(len(routes) * 0.8)
    train_routes = set(routes[:cut])
    train, dev = [], []
    for r, ps in by_route.items():
        if r in train_routes:
            train.extend(ps)
        else:
            dev.extend(ps)
    return train, dev


def main():
    train_all, dev_all = [], []
    for plat in INITIAL:
        segs = sorted((ROOT / "data" / "sim" / "segments" / plat).glob("**/sim.csv"))
        # Subsample for speed if huge
        if len(segs) > 200:
            rng = random.Random(13)
            segs_sub = rng.sample(segs, 200)
        else:
            segs_sub = segs
        tr, dv = route_split(segs_sub)
        print(f"{plat}: total={len(segs)} sub={len(segs_sub)} train={len(tr)} dev={len(dv)}")
        train_all.extend(tr)
        dev_all.extend(dv)

    result = fit(
        predict_factory,
        initial_coeffs=INITIAL,
        train_segments=train_all,
        dev_segments=dev_all,
        objective="yaw_plus_cte",
        bounds=BOUNDS,
        method="L-BFGS-B",
        max_iter=80,
        cte_weight=1.0,
        verbose=False,
    )
    print(format_fit_summary(result))

    # Save
    out = {
        "coeffs": result["coeffs"],
        "gates": PLATFORM_GATES,
        "train_obj": result["train_obj"],
        "dev_obj": result.get("dev_obj") or {},
    }
    with open(ROOT / "out" / "fitted_coeffs.json", "w") as f:
        json.dump(out, f, indent=2)
    print("\nSaved -> out/fitted_coeffs.json")


if __name__ == "__main__":
    main()
