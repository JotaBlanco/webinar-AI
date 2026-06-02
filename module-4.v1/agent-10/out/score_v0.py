"""Baseline V0 passthrough score."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-10")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "skills" / "score-model"))

from score import score, format_summary  # noqa: E402


def predict_v0(sim_df, platform):
    return sim_df[["yaw_rate_pred_rads"]].copy()


if __name__ == "__main__":
    r = score(predict_v0)
    print(format_summary(r))
