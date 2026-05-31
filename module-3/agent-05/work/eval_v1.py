"""Score V1 (fit) vs V0 on dev set AND full set."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "skills" / "make-train-dev-split"))
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "final-model"))

os.chdir(ROOT)

import pandas as pd
from score import score
from split import split
from predict import predict as v1_predict


def v0_predict(sim_df, platform):
    return pd.DataFrame(
        {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].values},
        index=sim_df.index,
    )


def report(label, result):
    print(f"\n{label}:")
    print(f"  yaw_rate_rmse: {result['yaw_rate_rmse']:.6f}")
    print(f"  cte_rmse:      {result['cte_rmse']:.3f}")
    print(f"  n_segments:    {result['n_segments']}")
    print(f"  failed:        {result.get('failed_segments', 0)}")
    print("  per_platform:")
    for pl, v in result["per_platform"].items():
        print(f"    {pl}: yr={v['yaw_rate_rmse']:.6f} cte={v['cte_rmse']:.3f} n={v['n_segments']}")
    print("  per_regime:")
    for r, v in result["per_regime"].items():
        print(f"    {r}: yr={v['yaw_rate_rmse']:.6f} n={v['n_samples']}")


def main():
    train, dev = split(dev_fraction=0.25, seed=42)

    print("=" * 60)
    print("DEV SET (held-out routes)")
    print("=" * 60)
    r0_dev = score(v0_predict, segment_paths=dev)
    r1_dev = score(v1_predict, segment_paths=dev)
    report("V0 (dev)", r0_dev)
    report("V1 (dev)", r1_dev)
    print(f"\n  yaw  delta: {r1_dev['yaw_rate_rmse'] - r0_dev['yaw_rate_rmse']:+.6f} "
          f"({(r1_dev['yaw_rate_rmse']/r0_dev['yaw_rate_rmse']-1)*100:+.1f}%)")
    print(f"  cte  delta: {r1_dev['cte_rmse'] - r0_dev['cte_rmse']:+.3f} "
          f"({(r1_dev['cte_rmse']/r0_dev['cte_rmse']-1)*100:+.1f}%)")

    print("\n" + "=" * 60)
    print("FULL SET (all Ford segments)")
    print("=" * 60)
    r0_all = score(v0_predict)
    r1_all = score(v1_predict)
    report("V0 (all)", r0_all)
    report("V1 (all)", r1_all)
    print(f"\n  yaw  delta: {r1_all['yaw_rate_rmse'] - r0_all['yaw_rate_rmse']:+.6f} "
          f"({(r1_all['yaw_rate_rmse']/r0_all['yaw_rate_rmse']-1)*100:+.1f}%)")
    print(f"  cte  delta: {r1_all['cte_rmse'] - r0_all['cte_rmse']:+.3f} "
          f"({(r1_all['cte_rmse']/r0_all['cte_rmse']-1)*100:+.1f}%)")


if __name__ == "__main__":
    main()
