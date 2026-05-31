"""Baseline score: V0 (yaw_rate_pred_rads passthrough) across all sim segments.

Uses the local score-model skill. Filters out segments without truth column.
"""
from __future__ import annotations
import sys
from pathlib import Path

REPO = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-03")
sys.path.insert(0, str(REPO / "skills" / "score-model"))
from score import score, format_summary  # noqa: E402


def passthrough(sim_df, platform):
    return sim_df[["yaw_rate_pred_rads"]].copy()


def gather_paths():
    root = REPO / "data" / "sim" / "segments"
    paths = sorted(root.glob("*/**/sim.csv"))
    # Filter out segments that lack yaw_rate_meas_rads (Tesla older schema)
    # Cheap-check: read the header.
    keep = []
    for p in paths:
        with p.open() as f:
            header = f.readline().rstrip("\n").split(",")
        if "yaw_rate_meas_rads" in header and "yaw_rate_pred_rads" in header:
            keep.append(p)
    return keep


if __name__ == "__main__":
    paths = gather_paths()
    print(f"Scoring {len(paths)} segments with truth.")
    result = score(passthrough, segment_paths=paths)
    print(format_summary(result))
