"""Bias-only fix: add per-platform constant to V1."""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-09")
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/"code")); sys.path.insert(0, str(ROOT/"_shared")); sys.path.insert(0, str(ROOT/"out"))

from v1_baseline import predict_v1
from harness import score_predict

# Computed from diagnose.py
BIASES = {
    "FORD_F_150_LIGHTNING_MK1": -0.001732,
    "FORD_MUSTANG_MACH_E_MK1":   0.001924,
    "HYUNDAI_IONIQ_5":           0.000512,
}

def predict(sim_df, platform):
    out = predict_v1(sim_df, platform)
    if platform in BIASES:
        out["yaw_rate_pred_rads"] = out["yaw_rate_pred_rads"] + BIASES[platform]
    return out

if __name__ == "__main__":
    print(json.dumps(score_predict(predict), indent=2))
