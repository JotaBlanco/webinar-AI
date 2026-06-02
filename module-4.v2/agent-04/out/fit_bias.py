"""Fit per-platform additive yaw-rate bias correction.

Computes mean(V1_yaw - truth_yaw) over training segments per platform.
Subtracting that constant from V1 output should reduce signed CTE drift.
"""
from __future__ import annotations
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-04")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "out"))
sys.path.insert(0, str(ROOT / "code"))
from v1_baseline import predict_v1
from score import find_segments, load_sim, ALLOW_COLS, PLATFORMS_WITH_TRUTH


def estimate_bias(platform: str, max_segs: int = 80):
    paths = find_segments(platform, split="train")[:max_segs]
    diffs = []
    for p in paths:
        df = load_sim(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        sim_df = df[ALLOW_COLS].copy()
        out = predict_v1(sim_df, platform)
        truth = df["yaw_rate_meas_rads"].to_numpy()
        pred = out["yaw_rate_pred_rads"].to_numpy()
        v = df["v_mps"].to_numpy()
        # Use moving-only samples
        mask = v > 5.0
        if mask.sum() > 0:
            diffs.append(np.mean(pred[mask] - truth[mask]))
    if not diffs:
        return 0.0
    return float(np.mean(diffs))


if __name__ == "__main__":
    biases = {}
    for plat in PLATFORMS_WITH_TRUTH:
        b = estimate_bias(plat)
        biases[plat] = b
        print(f"{plat}: bias={b:.6e}")
    out = ROOT / "out" / "platform_bias.json"
    out.write_text(json.dumps(biases, indent=2))
    print(f"wrote {out}")
