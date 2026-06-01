"""Score the final-model predict() using the local score-model skill,
against the sim-only segment tree (operating-contract enforced)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "final-model"))

# Important: score-model strips to the allowlist regardless, but we also want
# to compute trajectory truth (x_m, y_m) for CTE — that comes from the truth
# CSV the skill reads from data/sim/segments/<PLATFORM>/... by default.
# We pass explicit segment paths from data/sim/ so the skill can read truth.

from score import score, format_summary  # noqa: E402
from predict import predict  # noqa: E402


def main() -> None:
    sim_root = ROOT / "data" / "sim" / "segments"
    seg_paths = sorted(p for p in sim_root.glob("*/**/sim.csv") if p.is_file())
    print(f"# scoring {len(seg_paths)} segments")
    res = score(predict, segment_paths=seg_paths)
    print(format_summary(res, top_n=5))

    # Also dump per-platform for the report
    print("\n## raw per-platform")
    for plat, m in res["per_platform"].items():
        print(f"- {plat}: yaw_rmse={m['yaw_rate_rmse']:.5f}, "
              f"yaw_bias={m['yaw_residual_mean']:+.5f}, "
              f"cte_rmse={m['cte_rmse']:.3f}, n_seg={m['n_segments']}")


if __name__ == "__main__":
    main()
