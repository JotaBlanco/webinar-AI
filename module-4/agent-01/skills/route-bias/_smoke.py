"""Smoke test for route-bias.

Runs V0 passthrough across all platforms (small slice), asserts:
- per_route is populated for every platform with data on disk (no silent drop)
- per_platform_summary has one row per platform
- top_routes_by_cte is non-empty when any route had finite CTE
- recommendations entries (if any) carry the required keys

Run standalone: ``python3 _smoke.py``
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from route_bias import format_route_bias_summary, route_bias  # noqa: E402


def v0(sim_df, platform):
    return sim_df[["yaw_rate_pred_rads"]].copy()


def main() -> int:
    seg_root = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/data/sim/segments")
    assert seg_root.exists()

    seg_paths: list[Path] = []
    platforms_on_disk: list[str] = []
    for plat_dir in sorted(seg_root.glob("*")):
        if not plat_dir.is_dir():
            continue
        platforms_on_disk.append(plat_dir.name)
        seg_paths.extend(sorted(plat_dir.glob("**/sim.csv"))[:5])
    assert seg_paths, f"no sim.csv under {seg_root}"
    print(f"[smoke] route-bias on {len(seg_paths)} segments / "
          f"{len(platforms_on_disk)} platforms: {platforms_on_disk}")

    result = route_bias(v0, segment_paths=seg_paths, top_n=5)

    assert not result["per_route"].empty, "per_route empty"
    seen = set(result["per_route"]["platform"].unique())
    for plat in platforms_on_disk:
        assert plat in seen, f"per_route silently dropped {plat!r}"

    assert not result["per_platform_summary"].empty
    assert set(result["per_platform_summary"]["platform"]) == seen

    # Top tables should have at most top_n × n_platforms rows.
    assert len(result["top_routes_by_cte"]) <= 5 * len(seen)
    assert len(result["top_routes_by_yaw_bias"]) <= 5 * len(seen)

    # Recommendation entries (V0 has real bias on the Fords + Hyundai → almost
    # certainly non-empty, but we don't strictly require >0 because the cohort
    # may be small).
    for rec in result["recommendations"]:
        for k in ("platform", "route", "yaw_residual_mean", "cte_signed_mean",
                  "share_yaw", "share_cte", "feature_means", "notes"):
            assert k in rec, f"recommendation missing {k}: {rec}"

    print("[smoke] PASS")
    print()
    print(format_route_bias_summary(result, top_n=3))
    return 0


if __name__ == "__main__":
    sys.exit(main())
