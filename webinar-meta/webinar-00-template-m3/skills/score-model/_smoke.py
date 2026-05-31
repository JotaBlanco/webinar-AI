"""Smoke test for score-model.

Runs a trivial V0 passthrough on ~5 segments and asserts the returned dict
has the expected shape with non-degenerate KPI values.

Run standalone: ``python3 _smoke.py``
"""

from __future__ import annotations

import sys
from pathlib import Path
from pprint import pprint

# Make score.py importable when running this file directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from score import score  # noqa: E402


def v0(sim_df, platform):
    """Trivial passthrough: predict equals the baseline column already in sim.csv."""
    return sim_df[["yaw_rate_pred_rads"]].copy()


def main() -> int:
    seg_root = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/data/sim/segments/FORD_MUSTANG_MACH_E_MK1")
    seg_paths = sorted(seg_root.glob("**/sim.csv"))[:5]
    assert seg_paths, f"no sim.csv files found under {seg_root}"
    print(f"[smoke] scoring {len(seg_paths)} segments...")

    result = score(v0, segment_paths=seg_paths)

    # Shape assertions.
    for key in ("yaw_rate_rmse", "cte_rmse", "n_segments", "n_samples", "per_platform", "per_regime", "failed_segments"):
        assert key in result, f"missing key: {key}"

    assert result["n_segments"] > 0, "no segments scored"
    assert result["yaw_rate_rmse"] > 0, f"yaw_rate_rmse should be > 0, got {result['yaw_rate_rmse']}"
    assert result["cte_rmse"] > 0, f"cte_rmse should be > 0, got {result['cte_rmse']}"
    assert len(result["per_platform"]) >= 1, "per_platform should have at least one entry"
    assert "straight" in result["per_regime"], "per_regime should have a 'straight' key"

    print("[smoke] PASS")
    pprint(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
