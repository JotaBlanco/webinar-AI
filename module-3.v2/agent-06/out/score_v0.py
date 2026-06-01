"""Score V0 (passthrough of yaw_rate_pred_rads) and V1 (recipe defaults)."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-06")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "out"))

import pandas as pd
import numpy as np
from score import score, format_summary

# Override default segment paths to use sim-only (mirror of grading)
def _paths():
    root = ROOT / "data" / "sim-only" / "segments"
    return sorted(p for p in root.glob("*/**/sim.csv") if p.is_file())


def v0_predict(sim_df, platform):
    return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()}, index=sim_df.index)


paths = _paths()
print(f"# segments found: {len(paths)}")

# But score skill needs truth columns — sim-only has no truth!
# Use sim/ for scoring.
def _paths_truth():
    root = ROOT / "data" / "sim" / "segments"
    return sorted(p for p in root.glob("*/**/sim.csv") if p.is_file())

paths_t = _paths_truth()
print(f"# truth segments: {len(paths_t)}")

print("\n=== V0 baseline (truth-frame scoring) ===")
res = score(v0_predict, segment_paths=paths_t)
print(format_summary(res, top_n=3))

print("\n\n=== V1 recipe defaults ===")
from predict_v1 import predict as v1_predict
res = score(v1_predict, segment_paths=paths_t)
print(format_summary(res, top_n=3))
