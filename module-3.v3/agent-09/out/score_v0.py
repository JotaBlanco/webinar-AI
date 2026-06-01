"""Score V0 baseline to set floor."""
import sys
from pathlib import Path
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-09")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
from score import score, format_summary  # noqa


def predict_v0(sim_df, platform):
    return pd.DataFrame(
        {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
        index=sim_df.index,
    )


if __name__ == "__main__":
    # Use sim-only to mirror grading
    root = ROOT / "data" / "sim" / "segments"
    segs = sorted(p for p in root.glob("*/**/sim.csv") if p.is_file())
    print(f"Found {len(segs)} segments")
    # Patch score to use sim-only structure: the path-based platform extraction is parents[3]
    # since structure is data/sim-only/segments/<PLAT>/<dev>/<route>/<idx>/sim.csv same depth.
    res = score(predict_v0, segment_paths=segs)
    print(format_summary(res))
