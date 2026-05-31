"""Score the final-model/predict.py against sim/segments (truth available).

We point score-model at data/sim/segments/*/*/*/*/sim.csv. The skill itself
strips columns down to the agent-visible allowlist before calling predict —
so this run is contract-equivalent to the canonical grader, but evaluated
on the truth-bearing tree so we can compute RMSE.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-06")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "final-model"))

from score import score, format_summary  # noqa: E402
import predict as P  # noqa: E402


def baseline_predict(sim_df, platform):
    import pandas as pd
    out = pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()}, index=sim_df.index)
    return out


def main():
    paths = sorted((ROOT / "data" / "sim" / "segments").glob("*/*/*/*/sim.csv"))
    print(f"Scoring {len(paths)} segments")

    print("\n=== V0 baseline (passthrough) ===")
    r0 = score(baseline_predict, segment_paths=paths)
    print(format_summary(r0, top_n=3))

    print("\n=== V1 final-model ===")
    r1 = score(P.predict, segment_paths=paths)
    print(format_summary(r1, top_n=3))

    print("\n=== headline deltas ===")
    print(f"yaw_rmse: V0={r0['yaw_rate_rmse']:.6f} -> V1={r1['yaw_rate_rmse']:.6f}")
    print(f"cte_rmse: V0={r0['cte_rmse']:.4f} -> V1={r1['cte_rmse']:.4f}")


if __name__ == "__main__":
    main()
