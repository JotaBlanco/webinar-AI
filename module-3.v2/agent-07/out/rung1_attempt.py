"""Rung-1 attempt: linear dynamic single-track on Mach-E only.

Fit C_af per platform, hold other carParams constants. Log result.
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
sys.path.insert(0, str(ROOT / "code"))

from score import score, format_summary
from fit import fit, format_fit_summary
from parameters import MACH_E, F150_LIGHTNING


CARPARAMS = {
    "FORD_MUSTANG_MACH_E_MK1": dict(m=MACH_E.m, Iz=MACH_E.I_z, a=MACH_E.l_f, b=MACH_E.l_r,
                                    C_af=MACH_E.C_alpha_f, C_ar=MACH_E.C_alpha_r),
    "FORD_F_150_LIGHTNING_MK1": dict(m=F150_LIGHTNING.m, Iz=F150_LIGHTNING.I_z,
                                     a=F150_LIGHTNING.l_f, b=F150_LIGHTNING.l_r,
                                     C_af=F150_LIGHTNING.C_alpha_f, C_ar=F150_LIGHTNING.C_alpha_r),
}


def rung1_predict_factory(platform, coeffs):
    base = CARPARAMS[platform]
    C_af = coeffs["C_af"]
    C_ar = coeffs.get("C_ar", base["C_ar"])
    g = coeffs["g"]
    delta0 = coeffs["delta0"]
    m, Iz, a, b = base["m"], base["Iz"], base["a"], base["b"]

    def predict_arr(sim_df):
        delta = (sim_df["delta_road_rad"].to_numpy() - delta0) * g
        vx = sim_df["v_mps"].to_numpy()
        t = sim_df["t_s"].to_numpy()
        dt = np.diff(t, prepend=t[0])
        vx_safe = np.maximum(vx, 1.0)
        vy = 0.0
        yr = 0.0
        out = np.empty_like(vx)
        for i in range(len(vx)):
            alpha_f = delta[i] - (vy + a * yr) / vx_safe[i]
            alpha_r = -(vy - b * yr) / vx_safe[i]
            F_yf = C_af * alpha_f
            F_yr = C_ar * alpha_r
            vy_dot = (F_yf + F_yr) / m - vx[i] * yr
            yr_dot = (a * F_yf - b * F_yr) / Iz
            vy += vy_dot * dt[i]
            yr += yr_dot * dt[i]
            out[i] = yr
        return out
    return predict_arr


INIT = {
    "FORD_MUSTANG_MACH_E_MK1": {"C_af": 286_551.0, "C_ar": 355_912.0, "g": 0.891, "delta0": -0.0001},
}
BOUNDS = {
    "FORD_MUSTANG_MACH_E_MK1": {
        "C_af": (50_000.0, 600_000.0),
        "C_ar": (50_000.0, 700_000.0),
        "g": (0.5, 1.5),
        "delta0": (-0.02, 0.02),
    },
}


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
    plat = "FORD_MUSTANG_MACH_E_MK1"
    segs = sorted((ROOT / "data" / "sim" / "segments" / plat).glob("**/sim.csv"))
    # Subsample
    rng = random.Random(13)
    segs_sub = rng.sample(segs, min(80, len(segs)))
    tr, dv = route_split(segs_sub)
    print(f"{plat}: total={len(segs)} sub={len(segs_sub)} train={len(tr)} dev={len(dv)}")

    result = fit(
        rung1_predict_factory,
        initial_coeffs=INIT,
        train_segments=tr,
        dev_segments=dv,
        objective="yaw_plus_cte",
        bounds=BOUNDS,
        method="L-BFGS-B",
        max_iter=40,
        cte_weight=1.0,
        verbose=False,
    )
    print(format_fit_summary(result))

    # Score on full data
    fitted = result["coeffs"][plat]
    print(f"\nfitted coeffs: {fitted}")

    def predict(sim_df, platform):
        if platform != plat:
            return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
                                index=sim_df.index)
        cb = rung1_predict_factory(platform, fitted)
        yr = cb(sim_df)
        return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)

    segs_full = sorted((ROOT / "data" / "sim" / "segments" / plat).glob("**/sim.csv"))
    r2 = score(predict, segment_paths=segs_full)
    print(format_summary(r2))


if __name__ == "__main__":
    main()
