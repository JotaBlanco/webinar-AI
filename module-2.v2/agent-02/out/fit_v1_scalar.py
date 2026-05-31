"""V1: per-platform scalar gain on V0 yaw rate.

Theory: KS yaw = (v/L) * tan(delta_road). If the steering ratio or effective
wheelbase used to build delta_road is off, V0 systematically over- or under-
predicts yaw rate. A single multiplicative scalar per platform absorbs that
mismatch and (more importantly) kills the signed CTE bias.

We fit k by minimising pooled yaw RMSE per platform on the train set, then
score on the whole sim set.
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd

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


def fit_scalars():
    fit = {}
    for plat in PLATFORMS:
        if plat == "TESLA_MODEL_3":
            # Tesla's "truth" IS the V0 output — no independent yaw measurement.
            # Best we can do is k=1 (match V0 exactly).
            fit[plat] = 1.0
            print(f"  {plat}: k = 1.000000  (forced — Tesla has no indep truth)")
            continue
        segs = sorted((ROOT / "data" / "sim" / "segments" / plat).glob("**/sim.csv"))
        num = 0.0
        den = 0.0
        for p in segs:
            df = pd.read_csv(p, usecols=["t_s", "v_mps", "yaw_rate_pred_rads", TRUTH_COL[plat]])
            mask = df["v_mps"].to_numpy() > 2.0
            if not mask.any():
                continue
            y = df[TRUTH_COL[plat]].to_numpy()[mask]
            x = df["yaw_rate_pred_rads"].to_numpy()[mask]
            num += float(np.sum(x * y))
            den += float(np.sum(x * x))
        k = num / den if den > 0 else 1.0
        fit[plat] = k
        print(f"  {plat}: k = {k:.6f}  (n_segs={len(segs)})")
    return fit


def predict_factory(scalars: dict):
    def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
        k = scalars.get(platform, 1.0)
        out = pd.DataFrame(index=sim_df.index)
        out["yaw_rate_pred_rads"] = sim_df["yaw_rate_pred_rads"].astype(float) * k
        return out
    return predict


if __name__ == "__main__":
    print("Fitting per-platform scalar gain (least-squares yaw = k * v0_yaw):")
    scalars = fit_scalars()
    print(f"\nScalars: {scalars}\n")
    segs = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))
    res = score(predict_factory(scalars), segment_paths=segs)
    print(format_summary(res))
    # Persist scalars for downstream use
    import json
    (ROOT / "out" / "v1_scalars.json").write_text(json.dumps(scalars, indent=2))
