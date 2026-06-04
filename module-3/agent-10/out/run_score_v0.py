"""Score V0 baseline (pure passthrough)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
from score import score, format_summary  # noqa: E402


def predict_v0(sim_df, platform):
    return pd.DataFrame(
        {"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
        index=sim_df.index,
    )


def main() -> None:
    sim_root = ROOT / "data" / "sim" / "segments"
    seg_paths = sorted(p for p in sim_root.glob("*/**/sim.csv") if p.is_file())
    print(f"# V0 — scoring {len(seg_paths)} segments")
    res = score(predict_v0, segment_paths=seg_paths)
    print(format_summary(res, top_n=3))
    print("\n## V0 per-platform")
    for plat, m in res["per_platform"].items():
        print(f"- {plat}: yaw_rmse={m['yaw_rate_rmse']:.5f}, cte_rmse={m['cte_rmse']:.3f}")
    print(f"\n## V0 overall: yaw_rmse={res['yaw_rate_rmse']:.5f} cte_rmse={res['cte_rmse']:.3f}")


if __name__ == "__main__":
    main()
