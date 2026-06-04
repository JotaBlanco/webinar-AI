"""Score V0 baseline and the shipped model on sim-only segments."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-08")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "final-model"))

import pandas as pd
from score import score, format_summary  # type: ignore
from predict import predict as my_predict  # type: ignore


def v0_predict(sim_df, platform):
    return pd.DataFrame(
        {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
        index=sim_df.index,
    )


def sim_paths() -> list[Path]:
    root = ROOT / "data" / "sim" / "segments"
    return sorted(p for p in root.glob("*/**/sim.csv") if p.is_file())


def main():
    paths = sim_paths()
    print(f"Found {len(paths)} sim segments (with truth)")

    print("\n=== V0 BASELINE ===")
    r0 = score(v0_predict, segment_paths=paths)
    print(format_summary(r0))

    print("\n=== MY MODEL ===")
    r1 = score(my_predict, segment_paths=paths)
    print(format_summary(r1))

    print("\n=== HEADLINE DELTA ===")
    print(f"V0:   yaw={r0['yaw_rate_rmse']:.6f}  cte={r0['cte_rmse']:.4f}")
    print(f"Mine: yaw={r1['yaw_rate_rmse']:.6f}  cte={r1['cte_rmse']:.4f}")
    if r0['yaw_rate_rmse'] > 0:
        dy = (r0['yaw_rate_rmse'] - r1['yaw_rate_rmse']) / r0['yaw_rate_rmse'] * 100
        print(f"yaw improvement: {dy:+.1f}%")
    if r0['cte_rmse'] > 0:
        dc = (r0['cte_rmse'] - r1['cte_rmse']) / r0['cte_rmse'] * 100
        print(f"CTE improvement: {dc:+.1f}%")


if __name__ == "__main__":
    main()
