"""Smoke test for inspect-residuals.

Exercises both modes:
  1. 1-D inspect_residuals across ALL platforms (verifies schema-aware path
     handles Tesla — earlier versions skipped Tesla silently).
  2. 2-D inspect_residuals_2d on a delta × speed slice.

Asserts the residuals DataFrames are non-empty, the figures are built and
saved, and Tesla actually participates.

Run standalone: ``python3 _smoke.py``
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from inspect_residuals import inspect_residuals, inspect_residuals_2d  # noqa: E402


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
        seg_paths.extend(sorted(plat_dir.glob("**/sim.csv"))[:3])
    assert seg_paths, f"no sim.csv files under {seg_root}"

    print(f"[smoke] 1-D residuals across {len(seg_paths)} segments / "
          f"{len(platforms_on_disk)} platforms: {platforms_on_disk}")

    out1 = inspect_residuals(
        v0, x_feature="delta_road_rad",
        segment_paths=seg_paths, bins=10,
    )
    assert not out1["residuals"].empty, "1-D residuals empty"
    assert not out1["binned"].empty, "1-D binned empty"
    # Tesla must participate — earlier silent-skip bug.
    seen = set(out1["residuals"]["platform"].unique())
    for plat in platforms_on_disk:
        assert plat in seen, (
            f"1-D mode silently dropped {plat!r}; skipped_by_platform="
            f"{out1.get('skipped_by_platform')}"
        )

    fig1 = out1["figure"]
    assert fig1.axes[0].get_xlabel() == "delta_road_rad"
    tmp1 = Path(tempfile.gettempdir()) / "inspect_residuals_1d_smoke.png"
    fig1.savefig(tmp1, dpi=100)
    assert tmp1.exists() and tmp1.stat().st_size > 0
    print(f"[smoke] 1-D wrote {tmp1} ({tmp1.stat().st_size} bytes)")

    # ---- 2-D ----
    print(f"[smoke] 2-D residuals (delta_road_rad × v_mps)")
    out2 = inspect_residuals_2d(
        v0,
        x_feature="delta_road_rad",
        y_feature="v_mps",
        segment_paths=seg_paths,
        bins=(15, 15),
        min_cell_n=3,
    )
    assert not out2["residuals"].empty, "2-D residuals empty"
    assert out2["heatmaps"], "no heatmaps built"
    # Every platform with data on disk should also have a heatmap.
    for plat in platforms_on_disk:
        assert plat in out2["heatmaps"], (
            f"2-D heatmap missing for {plat!r}; skipped_by_platform="
            f"{out2.get('skipped_by_platform')}"
        )

    fig2 = out2["figure"]
    tmp2 = Path(tempfile.gettempdir()) / "inspect_residuals_2d_smoke.png"
    fig2.savefig(tmp2, dpi=100)
    assert tmp2.exists() and tmp2.stat().st_size > 0
    print(f"[smoke] 2-D wrote {tmp2} ({tmp2.stat().st_size} bytes)")

    print(f"[smoke] 1-D residuals: {len(out1['residuals']):,} rows, "
          f"{out1['residuals']['platform'].nunique()} platforms")
    print(f"[smoke] 2-D heatmaps:  {list(out2['heatmaps'].keys())}")
    print("[smoke] PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
