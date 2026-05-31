"""Score the V0 baseline (yaw_rate_pred_rads already in CSV) using score-model skill."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "skills" / "make-train-dev-split"))

from score import score  # noqa: E402
from split import split  # noqa: E402


def predict_v0(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
    # passthrough: use the precomputed yaw_rate_pred_rads
    return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
                        index=sim_df.index)


if __name__ == "__main__":
    import os
    os.chdir(ROOT)

    train, dev = split(dev_fraction=0.25, seed=42)
    print(f"Train segments: {len(train)}  Dev segments: {len(dev)}")

    print("\n=== V0 — dev set ===")
    res = score(predict_v0, segment_paths=dev)
    print(f"Overall: yaw_RMSE={res['yaw_rate_rmse']:.6f}  CTE_RMSE={res['cte_rmse']:.3f}")
    for plat, sub in res["per_platform"].items():
        print(f"  {plat}: yaw_RMSE={sub['yaw_rate_rmse']:.6f}  CTE_RMSE={sub['cte_rmse']:.3f}  n_seg={sub['n_segments']}")
    for reg, sub in res["per_regime"].items():
        print(f"  regime {reg}: yaw_RMSE={sub['yaw_rate_rmse']:.6f}  n={sub['n_samples']}")

    print("\n=== V0 — full data ===")
    res2 = score(predict_v0)
    print(f"Overall: yaw_RMSE={res2['yaw_rate_rmse']:.6f}  CTE_RMSE={res2['cte_rmse']:.3f}")
    for plat, sub in res2["per_platform"].items():
        print(f"  {plat}: yaw_RMSE={sub['yaw_rate_rmse']:.6f}  CTE_RMSE={sub['cte_rmse']:.3f}  n_seg={sub['n_segments']}")
