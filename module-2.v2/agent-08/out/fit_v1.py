"""Fit per-platform understeer-corrected yaw model.

Model: yaw_pred = (G * yaw_v0) / (1 + Kus * v^2) + bias

where yaw_v0 is the V0 baseline (KS geometry). Optimised against the
yaw_plus_cte blend so the CTE drift on Ford F-150 and Hyundai gets pulled in.

Tesla is held at V0 (gain=1, Kus=0, bias=0) because Tesla truth IS V0.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-08")
os.chdir(str(ROOT))
sys.path.insert(0, str(ROOT / "skills" / "fit-model"))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))

from fit import fit, format_fit_summary
from score import score, format_summary, PLATFORM_SCHEMA


def predict_factory(platform: str, coeffs: dict):
    G    = float(coeffs.get("G", 1.0))
    Kus  = float(coeffs.get("Kus", 0.0))
    bias = float(coeffs.get("bias", 0.0))

    def predict(sim_df: pd.DataFrame) -> np.ndarray:
        v   = sim_df["v_mps"].to_numpy(dtype=float)
        yv0 = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        return (G * yv0) / (1.0 + Kus * v * v) + bias

    return predict


def all_segments():
    root = ROOT / "data" / "sim" / "segments"
    return sorted(p for p in root.glob("*/**/sim.csv") if p.is_file())


def main():
    segs = all_segments()
    # split per-platform train/dev: we'll just use all for train (small).
    init = {
        "FORD_F_150_LIGHTNING_MK1": {"G": 1.0, "Kus": 0.0, "bias": 0.0},
        "FORD_MUSTANG_MACH_E_MK1":  {"G": 1.0, "Kus": 0.0, "bias": 0.0},
        "HYUNDAI_IONIQ_5":          {"G": 1.0, "Kus": 0.0, "bias": 0.0},
    }
    bounds = {
        p: {"G": (0.5, 1.5), "Kus": (-0.01, 0.02), "bias": (-0.02, 0.02)}
        for p in init
    }
    result = fit(
        predict_factory,
        init,
        train_segments=segs,
        objective="yaw_plus_cte",
        bounds=bounds,
        method="L-BFGS-B",
        max_iter=80,
        cte_weight=2.0,
        verbose=False,
    )
    print(format_fit_summary(result))

    # Save coeffs (Tesla stays identity).
    coeffs = result["coeffs"]
    coeffs["TESLA_MODEL_3"] = {"G": 1.0, "Kus": 0.0, "bias": 0.0}
    (ROOT / "out" / "coeffs_v1.json").write_text(json.dumps(coeffs, indent=2))
    print("Saved coeffs to out/coeffs_v1.json")

    # Score the model end-to-end.
    def predict_v1(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
        c = coeffs.get(platform, {"G": 1.0, "Kus": 0.0, "bias": 0.0})
        cb = predict_factory(platform, c)
        return pd.DataFrame({"yaw_rate_pred_rads": cb(sim_df)}, index=sim_df.index)

    res = score(predict_v1)
    print()
    print(format_summary(res, top_n=5))


if __name__ == "__main__":
    main()
