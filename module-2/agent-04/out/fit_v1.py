"""V1 fit: per-platform understeer model.

Model:  yr_pred = v * delta_road / (L_eff + Kus * v^2) + bias

This calibrates wheelbase and understeer gradient per platform. For platforms
without independent truth (Tesla), we pass through V0.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-04")
sys.path.insert(0, str(ROOT / "skills" / "fit-model"))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))

from fit import fit, format_fit_summary  # noqa: E402

# Per-platform L priors (wheelbases from parameters.py)
L_PRIOR = {
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "FORD_MUSTANG_MACH_E_MK1":  2.984,
    "HYUNDAI_IONIQ_5":          3.00,  # approximate; Ioniq 5 wheelbase is 3.00m
}


def predict_factory(platform, coeffs):
    if platform == "TESLA_MODEL_3":
        def predict(sim_df):
            return sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        return predict

    L_eff = coeffs["L_eff"]
    Kus = coeffs["Kus"]
    bias = coeffs["bias"]

    def predict(sim_df):
        v = sim_df["v_mps"].to_numpy(dtype=float)
        d = sim_df["delta_road_rad"].to_numpy(dtype=float)
        denom = L_eff + Kus * v * v
        return v * d / denom + bias

    return predict


def main():
    seg_root = ROOT / "data" / "sim" / "segments"
    # Build train/dev split by route hash
    all_paths = sorted(p for p in seg_root.glob("*/**/sim.csv") if p.is_file())
    # 80/20 split by route id (parents[1].name)
    train, dev = [], []
    for p in all_paths:
        route = p.resolve().parents[1].name
        h = hash(route) & 0xff
        if h < 200:
            train.append(p)
        else:
            dev.append(p)

    print(f"train={len(train)} dev={len(dev)}")

    init = {}
    bounds = {}
    for plat in ("FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"):
        init[plat] = {"L_eff": L_PRIOR[plat], "Kus": 0.001, "bias": 0.0}
        bounds[plat] = {
            "L_eff": (1.5, 5.0),
            "Kus": (-0.005, 0.02),
            "bias": (-0.02, 0.02),
        }
    # Tesla passthrough — single dummy coef
    init["TESLA_MODEL_3"] = {"dummy": 0.0}
    bounds["TESLA_MODEL_3"] = {"dummy": (-1.0, 1.0)}

    result = fit(
        predict_factory, init, train_segments=train,
        objective="yaw_plus_cte", dev_segments=dev,
        bounds=bounds, cte_weight=1.0, max_iter=80,
    )
    print(format_fit_summary(result))

    # Save coeffs
    out = ROOT / "out" / "coeffs_v1.json"
    with out.open("w") as f:
        json.dump(result["coeffs"], f, indent=2)
    print(f"saved → {out}")


if __name__ == "__main__":
    main()
