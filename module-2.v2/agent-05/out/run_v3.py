"""V3 scoring."""
from __future__ import annotations
import sys, os, json
from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-05")
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
from score import score, format_summary  # noqa: E402

COEFFS = json.loads((ROOT / "out" / "v3_coeffs.json").read_text())
FEATURES = ["yv0","v","d","vd","v2d","d3","vd3","v2d3","sr","vsr","d_abs_d","a_long"]

def predict_v3(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
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
    a_long = (sim_df["a_long_mps2"].astype(float).to_numpy()
              if "a_long_mps2" in sim_df.columns else np.zeros_like(v))
    feats = {
        "yv0": yv0, "v": v, "d": d, "vd": v*d, "v2d": v*v*d, "d3": d**3,
        "vd3": v*d**3, "v2d3": v*v*d**3, "sr": sr, "vsr": v*sr,
        "d_abs_d": d*np.abs(d), "a_long": a_long,
    }
    yp = c["intercept"] + sum(c[n] * feats[n] for n in FEATURES)
    out["yaw_rate_pred_rads"] = yp
    return out

if __name__ == "__main__":
    result = score(predict_v3)
    print(format_summary(result))
