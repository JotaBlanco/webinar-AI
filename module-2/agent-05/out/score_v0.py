"""Score V0 baseline (yaw_rate_pred_rads passthrough)."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-05")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
from score import score, format_summary  # type: ignore


def v0_predict(sim_df, platform):
    out = sim_df[["yaw_rate_pred_rads"]].copy()
    return out


if __name__ == "__main__":
    import os
    os.chdir(ROOT)
    result = score(v0_predict)
    print(format_summary(result))
