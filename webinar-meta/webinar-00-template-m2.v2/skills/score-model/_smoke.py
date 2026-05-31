"""Smoke test for score-model.

Runs a trivial V0 passthrough on ~5 segments and asserts the returned dict
has every expected key with non-degenerate values. Prints the dashboard.

Run standalone: ``python3 _smoke.py``
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score import score, format_summary  # noqa: E402


def v0(sim_df, platform):
    """Trivial passthrough: predict equals the baseline column already in sim.csv."""
    return sim_df[["yaw_rate_pred_rads"]].copy()


def main() -> int:
    seg_root = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/data/sim/segments/FORD_MUSTANG_MACH_E_MK1")
    seg_paths = sorted(seg_root.glob("**/sim.csv"))[:5]
    assert seg_paths, f"no sim.csv files found under {seg_root}"
    print(f"[smoke] scoring {len(seg_paths)} segments...")

    result = score(v0, segment_paths=seg_paths, top_n=3)

    expected = (
        "yaw_rate_rmse", "cte_rmse", "n_segments", "n_samples", "failed_segments",
        "per_platform", "per_regime", "per_segment", "per_route",
        "worst_segments_by_cte", "worst_segments_by_yaw",
        "yaw_rmse_distribution", "cte_rmse_distribution",
    )
    for key in expected:
        assert key in result, f"missing key: {key}"

    assert result["n_segments"] > 0, "no segments scored"
    assert result["yaw_rate_rmse"] > 0
    assert result["cte_rmse"] > 0
    assert len(result["per_platform"]) >= 1
    assert "straight" in result["per_regime"]
    assert len(result["per_segment"]) == result["n_segments"]
    assert "yaw_residual_mean" in result["per_segment"].columns
    assert "cte_signed_mean" in result["per_segment"].columns
    assert len(result["worst_segments_by_cte"]) <= 3

    print("[smoke] PASS")
    print()
    print(format_summary(result, top_n=3))
    return 0


if __name__ == "__main__":
    sys.exit(main())
