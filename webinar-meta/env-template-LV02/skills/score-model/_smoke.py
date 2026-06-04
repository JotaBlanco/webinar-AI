"""Smoke test for score-model.

Runs a trivial V0 passthrough on a few segments from EVERY platform under
`data/sim/segments/` and asserts:

- the returned dict has every expected key with non-degenerate values
- every platform that has sample data is scored (no silent skips from
  schema mismatch — that was the M2-cohort bug)
- the per-platform `truth_col` matches PLATFORM_SCHEMA
- the bias-warnings list is well-formed
- the formatted summary renders without error

Run standalone: ``python3 _smoke.py``
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from score import (  # noqa: E402
    PLATFORM_SCHEMA,
    bias_warnings,
    format_summary,
    score,
)


def v0(sim_df, platform):
    """Trivial passthrough: predict equals the baseline column already in sim.csv."""
    return sim_df[["yaw_rate_pred_rads"]].copy()


def main() -> int:
    seg_root = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/data/sim/segments")
    assert seg_root.exists(), f"sim/segments root not found: {seg_root}"

    # Take a handful of segments from EVERY platform present on disk.
    seg_paths: list[Path] = []
    platforms_on_disk: list[str] = []
    for plat_dir in sorted(seg_root.glob("*")):
        if not plat_dir.is_dir():
            continue
        platforms_on_disk.append(plat_dir.name)
        seg_paths.extend(sorted(plat_dir.glob("**/sim.csv"))[:3])
    assert seg_paths, f"no sim.csv files found under {seg_root}"
    assert len(platforms_on_disk) >= 2, "need at least 2 platforms to exercise schema"

    print(f"[smoke] scoring {len(seg_paths)} segments across "
          f"{len(platforms_on_disk)} platforms: {platforms_on_disk}")

    result = score(v0, segment_paths=seg_paths, top_n=3)

    expected = (
        "yaw_rate_rmse", "cte_rmse", "n_segments", "n_samples", "failed_segments",
        "failed_by_platform", "platforms_seen",
        "per_platform", "per_regime", "per_segment", "per_route",
        "worst_segments_by_cte", "worst_segments_by_yaw",
        "yaw_rmse_distribution", "cte_rmse_distribution",
        "bias_warnings",
    )
    for key in expected:
        assert key in result, f"missing key: {key}"

    assert result["n_segments"] > 0, "no segments scored"
    assert len(result["per_platform"]) >= 1
    assert "straight" in result["per_regime"]
    assert len(result["per_segment"]) == result["n_segments"]
    assert "yaw_residual_mean" in result["per_segment"].columns
    assert "cte_signed_mean" in result["per_segment"].columns
    assert len(result["worst_segments_by_cte"]) <= 3

    # Schema-aware sanity checks ------------------------------------------------
    # Every platform that has data on disk and is in the schema must appear in
    # the result (no silent drop).
    scored = set(result["per_platform"].keys())
    for plat in platforms_on_disk:
        if plat in PLATFORM_SCHEMA:
            assert plat in scored, (
                f"platform {plat!r} present on disk and in PLATFORM_SCHEMA "
                f"but missing from per_platform — schema-aware loop is silently dropping it. "
                f"failed_by_platform: {result['failed_by_platform']}"
            )
    # Each scored platform should report the truth_col its schema defines.
    for plat, m in result["per_platform"].items():
        expected_truth = PLATFORM_SCHEMA.get(plat, {}).get("truth_col")
        if expected_truth is not None:
            assert m["truth_col"] == expected_truth, (
                f"{plat} truth_col={m['truth_col']!r}, schema says {expected_truth!r}"
            )

    # bias_warnings() should agree with what score() returned.
    direct = bias_warnings(result["per_platform"])
    assert direct == result["bias_warnings"], "bias_warnings drift between score() and helper"
    for w in result["bias_warnings"]:
        assert w["severity"] in ("warn", "high")
        assert w["metric"] in ("yaw_residual_mean", "cte_signed_mean")

    print("[smoke] PASS")
    print()
    print(format_summary(result, top_n=3))
    return 0


if __name__ == "__main__":
    sys.exit(main())
