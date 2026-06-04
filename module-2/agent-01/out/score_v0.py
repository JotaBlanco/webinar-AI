"""Score V0 baseline (yaw_rate_pred_rads as-is) across all platforms."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-01")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
from score import score, format_summary  # noqa: E402


def v0_predict(sim_df, platform):
    import pandas as pd
    return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
                        index=sim_df.index)


if __name__ == "__main__":
    seg_paths = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))
    print(f"found {len(seg_paths)} segments")
    res = score(v0_predict, segment_paths=seg_paths)
    print(format_summary(res))
