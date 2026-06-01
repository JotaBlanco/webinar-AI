"""Fit V2: kinematic + understeer + steering-rate lead + bias.

Per platform we fit:
    yaw = v * sin(delta_road + tau * d_delta_dt) / L_eff / (1 + K_us * v^2) + bias

(Linearized + lead term — captures understeer curve AND pipeline-delay lead.)

Tesla → V0 passthrough.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-05")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "skills" / "fit-model"))
sys.path.insert(0, str(ROOT / "skills" / "make-train-dev-split"))
from score import score, format_summary  # type: ignore
from fit import fit, format_fit_summary  # type: ignore
from split import split  # type: ignore


PLATFORMS = ("FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5")

# Physical wheelbase priors from parameters.py.
L_PRIOR = {
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "FORD_MUSTANG_MACH_E_MK1":  2.984,
    "HYUNDAI_IONIQ_5":          2.984,  # not in parameters.py — use mid-size guess; will be fit
    "TESLA_MODEL_3":            2.875,
}


def _delta_dot(t, delta):
    """Time-derivative of delta_road with light smoothing."""
    return np.gradient(delta, t)


def predict_factory_v2(platform, coeffs):
    L_eff = coeffs.get("L_eff", L_PRIOR.get(platform, 3.0))
    K_us  = coeffs.get("K_us", 0.0)
    tau   = coeffs.get("tau", 0.0)
    bias  = coeffs.get("bias", 0.0)

    def predict(sim_df):
        if platform == "TESLA_MODEL_3":
            return sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        t = sim_df["t_s"].to_numpy(dtype=float)
        v = sim_df["v_mps"].to_numpy(dtype=float)
        d = sim_df["delta_road_rad"].to_numpy(dtype=float)
        d_dot = _delta_dot(t, d)
        d_eff = d + tau * d_dot
        # Understeer-shaped: v * tan(d_eff) / (L + Kus * v^2). Linearize tan for stability.
        num = v * np.tan(d_eff)
        den = L_eff + K_us * v * v
        return num / den + bias

    return predict


def main():
    import os
    os.chdir(ROOT)

    all_paths = sorted(Path("data/sim/segments").glob("*/**/sim.csv"))
    train, dev = split(all_paths, dev_fraction=0.25, seed=42)
    print(f"train={len(train)} dev={len(dev)}")

    init = {plat: {
        "L_eff": L_PRIOR[plat],
        "K_us":  0.001,
        "tau":   -0.05,   # negative = lead (sensor delay correction)
        "bias":  0.0,
    } for plat in PLATFORMS}

    bounds = {plat: {
        "L_eff": (1.5, 6.0),
        "K_us":  (-0.005, 0.015),
        "tau":   (-0.30, 0.30),
        "bias":  (-0.02, 0.02),
    } for plat in PLATFORMS}

    print("=== Fit pass 1: yaw_plus_cte (cte_weight=1.5) ===")
    result = fit(
        predict_factory_v2,
        init,
        train_segments=train,
        objective="yaw_plus_cte",
        dev_segments=dev,
        bounds=bounds,
        max_iter=120,
        cte_weight=1.5,
        verbose=False,
    )
    print(format_fit_summary(result))

    coeffs = result["coeffs"]
    coeffs["TESLA_MODEL_3"] = {"L_eff": L_PRIOR["TESLA_MODEL_3"], "K_us": 0.0, "tau": 0.0, "bias": 0.0}
    out_path = ROOT / "out" / "coeffs_v2.json"
    out_path.write_text(json.dumps(coeffs, indent=2))
    print(f"\nSaved coeffs → {out_path}")

    def predict_fn(sim_df, platform):
        cb = predict_factory_v2(platform, coeffs.get(platform, init.get(platform, {})))
        yr = cb(sim_df)
        return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)

    print("\n=== Full-dataset score V2 ===")
    res = score(predict_fn)
    print(format_summary(res))


if __name__ == "__main__":
    main()
