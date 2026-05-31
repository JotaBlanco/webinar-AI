"""Smoke test for inspect-residuals.

Runs V0 passthrough on ~10 Mach-E segments, asserts the residuals DataFrame
is non-empty and the figure is built. Writes the PNG to a temp file.

Run standalone: ``python3 _smoke.py``
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from inspect_residuals import inspect_residuals  # noqa: E402


def v0(sim_df, platform):
    return sim_df[["yaw_rate_pred_rads"]].copy()


def main() -> int:
    seg_root = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/data/sim-full/FORD_MUSTANG_MACH_E_MK1")
    seg_paths = sorted(seg_root.glob("**/sim.csv"))[:10]
    assert seg_paths, f"no sim.csv files found under {seg_root}"
    print(f"[smoke] inspecting residuals on {len(seg_paths)} segments...")

    out = inspect_residuals(v0, x_feature="delta_road_rad", segment_paths=seg_paths, bins=10)

    assert not out["residuals"].empty, "residuals DataFrame is empty"
    assert not out["binned"].empty, "binned DataFrame is empty"
    assert out["n_segments_used"] == len(seg_paths), \
        f"expected {len(seg_paths)} used, got {out['n_segments_used']}"
    assert out["n_segments_skipped"] == 0

    # Smoke the figure: it should have at least one Axes with the right xlabel.
    fig = out["figure"]
    assert len(fig.axes) >= 1
    ax = fig.axes[0]
    assert ax.get_xlabel() == "delta_road_rad"

    tmp = Path(tempfile.gettempdir()) / "inspect_residuals_smoke.png"
    fig.savefig(tmp, dpi=110)
    assert tmp.exists() and tmp.stat().st_size > 0
    print(f"[smoke] wrote {tmp} ({tmp.stat().st_size} bytes)")

    print(f"[smoke] residuals: {len(out['residuals']):,} rows across "
          f"{out['residuals']['platform'].nunique()} platform(s)")
    print(f"[smoke] binned head:")
    print(out["binned"].head().to_string(index=False))
    print("[smoke] PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
