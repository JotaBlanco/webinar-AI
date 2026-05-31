"""Score the V0 baseline (passthrough yaw_rate_pred_rads)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
import pandas as pd
from score import score, format_summary  # noqa


def v0(sim_df, platform):
    return sim_df[["yaw_rate_pred_rads"]].copy()


if __name__ == "__main__":
    # Force segment paths from absolute location (not cwd)
    import glob
    paths = sorted(glob.glob(str(ROOT / "data" / "sim" / "segments" / "*" / "**" / "sim.csv"), recursive=True))
    print(f"Found {len(paths)} segments")
    result = score(v0, segment_paths=paths)
    print(format_summary(result))
