"""V0 baseline scoring: just return yaw_rate_pred_rads (KS already pre-computed)."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-05")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "_shared"))

from score import score, format_summary  # noqa: E402
import pandas as pd  # noqa: E402


def predict_v0(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    out = pd.DataFrame(index=sim_df.index)
    out["yaw_rate_pred_rads"] = sim_df["yaw_rate_pred_rads"].astype(float)
    return out


if __name__ == "__main__":
    # Default segment glob from cwd
    import os
    os.chdir(ROOT)
    result = score(predict_v0)
    print(format_summary(result))
