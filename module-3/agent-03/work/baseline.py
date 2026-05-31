"""Establish V0 baseline KPIs using built-in `yaw_rate_pred_rads` channel."""
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-03")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "skills" / "make-train-dev-split"))
sys.path.insert(0, str(ROOT / "_shared"))

import os
os.chdir(ROOT)

import pandas as pd
from score import score
from split import split


def predict_v0(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
                        index=sim_df.index)


if __name__ == "__main__":
    train, dev = split()
    print(f"train={len(train)}  dev={len(dev)}")
    res_all = score(predict_v0)
    print("ALL FORD V0:", {k: v for k, v in res_all.items() if k != "per_platform" and k != "per_regime"})
    print("per_platform:", res_all["per_platform"])
    print("per_regime:", res_all["per_regime"])

    res_dev = score(predict_v0, segment_paths=dev)
    print("DEV V0:", {k: v for k, v in res_dev.items() if k != "per_platform" and k != "per_regime"})
    print("DEV per_platform:", res_dev["per_platform"])
