"""V1: per-platform affine correction to yaw_v0."""
from __future__ import annotations
import sys, os, json
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-05")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
from score import score, format_summary  # noqa: E402

COEFFS = json.loads((ROOT / "out" / "v1_coeffs.json").read_text())

def predict_v1(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = pd.DataFrame(index=sim_df.index)
    yv0 = sim_df["yaw_rate_pred_rads"].astype(float).to_numpy()
    v   = sim_df["v_mps"].astype(float).to_numpy()
    d   = sim_df["delta_road_rad"].astype(float).to_numpy()
    c = COEFFS.get(platform)
    if c is None or platform == "TESLA_MODEL_3":
        out["yaw_rate_pred_rads"] = yv0
        return out
    yp = c["a"] * yv0 + c["b_v"] * v + c["c_delta"] * d + c["d"]
    out["yaw_rate_pred_rads"] = yp
    return out

if __name__ == "__main__":
    result = score(predict_v1)
    print(format_summary(result))
