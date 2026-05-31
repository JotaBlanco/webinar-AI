"""V2: richer per-platform feature regression."""
from __future__ import annotations
import sys, os, json
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-05")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
from score import score, format_summary  # noqa: E402

COEFFS = json.loads((ROOT / "out" / "v2_coeffs.json").read_text())

def predict_v2(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = pd.DataFrame(index=sim_df.index)
    yv0 = sim_df["yaw_rate_pred_rads"].astype(float).to_numpy()
    if platform == "TESLA_MODEL_3" or COEFFS.get(platform) is None:
        out["yaw_rate_pred_rads"] = yv0
        return out
    c = COEFFS[platform]
    v = sim_df["v_mps"].astype(float).to_numpy()
    d = sim_df["delta_road_rad"].astype(float).to_numpy()
    t = sim_df["t_s"].astype(float).to_numpy()
    if "steer_rate_dps" in sim_df.columns:
        sr = sim_df["steer_rate_dps"].astype(float).to_numpy() * np.pi / 180.0
    else:
        sr = np.gradient(d, t) if len(t) > 1 else np.zeros_like(d)
    yp = (c["yv0"]*yv0 + c["d"]*d + c["vd"]*(v*d) + c["v2d"]*(v*v*d)
          + c["d3"]*(d**3) + c["sr"]*sr + c["intercept"])
    out["yaw_rate_pred_rads"] = yp
    return out

if __name__ == "__main__":
    result = score(predict_v2)
    print(format_summary(result))
