"""Fit V1: per-platform affine V0 correction yaw = gain*v0 + bias.

Tesla stays passthrough (no truth, won't change anything).
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-05")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "skills" / "fit-model"))
sys.path.insert(0, str(ROOT / "skills" / "make-train-dev-split"))
from score import score, format_summary  # type: ignore
from fit import fit, format_fit_summary  # type: ignore
from split import split  # type: ignore


PLATFORMS = ("FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5")


def predict_factory_v1(platform, coeffs):
    """Affine V0 correction. Tesla → passthrough."""
    gain = coeffs.get("gain", 1.0)
    bias = coeffs.get("bias", 0.0)

    def predict(sim_df):
        v0 = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        if platform == "TESLA_MODEL_3":
            return v0
        return gain * v0 + bias

    return predict


def main():
    import os
    os.chdir(ROOT)

    all_paths = sorted(Path("data/sim/segments").glob("*/**/sim.csv"))
    train, dev = split(all_paths, dev_fraction=0.25, seed=42)
    print(f"train={len(train)} dev={len(dev)}")

    init = {plat: {"gain": 1.0, "bias": 0.0} for plat in PLATFORMS}
    bounds = {plat: {"gain": (0.5, 1.5), "bias": (-0.05, 0.05)} for plat in PLATFORMS}

    result = fit(
        predict_factory_v1,
        init,
        train_segments=train,
        objective="yaw_plus_cte",
        dev_segments=dev,
        bounds=bounds,
        max_iter=80,
        cte_weight=2.0,
        verbose=False,
    )
    print(format_fit_summary(result))

    # Save coeffs
    coeffs = result["coeffs"]
    coeffs["TESLA_MODEL_3"] = {"gain": 1.0, "bias": 0.0}
    out_path = ROOT / "out" / "coeffs_v1.json"
    out_path.write_text(json.dumps(coeffs, indent=2))
    print(f"\nSaved coeffs → {out_path}")

    # Score on FULL dataset (sanity)
    def predict_fn(sim_df, platform):
        cb = predict_factory_v1(platform, coeffs.get(platform, {"gain": 1.0, "bias": 0.0}))
        yr = cb(sim_df)
        import pandas as pd
        return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)

    print("\n=== Full-dataset score V1 ===")
    res = score(predict_fn)
    print(format_summary(res))


if __name__ == "__main__":
    main()
