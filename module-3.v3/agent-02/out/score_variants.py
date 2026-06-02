"""Score all variants against V1 baseline."""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v3/agent-02")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "out"))

from scoring import score_predict_fn, print_score
import v1_baseline

COEFFS = json.loads((ROOT / "out" / "fitted_coeffs.json").read_text())


def _ddelta(t, delta):
    dd = np.gradient(delta, t)
    return np.clip(dd, -2.0, 2.0)


def make_predict(variant):
    def predict(sim_df, platform):
        v1_out = v1_baseline.predict_v1(sim_df, platform)
        yr_v1 = v1_out["yaw_rate_pred_rads"].to_numpy()
        if platform not in COEFFS:
            return v1_out
        c = COEFFS[platform][variant]
        v = sim_df["v_mps"].to_numpy()
        t = sim_df["t_s"].to_numpy()
        delta = sim_df["delta_road_rad"].to_numpy()
        if variant == "affine":
            yr = c["a"] * yr_v1 + c["b"]
        elif variant == "saturation":
            a_lat = v * yr_v1
            yr = c["a"] * yr_v1 + c["b"] + c["c"] * yr_v1 * a_lat * a_lat
        elif variant == "steering_rate":
            yr = c["a"] * yr_v1 + c["b"] + c["c"] * _ddelta(t, delta)
        elif variant == "combined":
            a_lat = v * yr_v1
            yr = c["a"] * yr_v1 + c["b"] + c["c"] * yr_v1 * a_lat * a_lat + c["d"] * _ddelta(t, delta)
        else:
            yr = yr_v1
        return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)
    return predict


if __name__ == "__main__":
    print_score(score_predict_fn(v1_baseline.predict_v1), "V1 baseline")
    for v in ["affine", "saturation", "steering_rate", "combined"]:
        print_score(score_predict_fn(make_predict(v)), f"V1 + {v}")
