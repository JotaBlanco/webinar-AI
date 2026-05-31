"""Smoke test for visualise-segment.

Runs `plot` on the first available FORD segment with a trivial V0 passthrough
and asserts the PNG was written and is non-empty.
"""

from __future__ import annotations

from pathlib import Path

from visualise import plot

SEGMENT_ROOT = Path(
    "/Users/javiquix/Desktop/quixdev/webinar-AI/data/sim/segments/FORD_MUSTANG_MACH_E_MK1"
)
OUT_PATH = Path("/tmp/visualise_segment_smoke.png")


def v0(sim_df, platform):
    """Trivial passthrough: predicted yaw rate = the column already on disk."""
    return sim_df[["yaw_rate_pred_rads"]].copy()


def main():
    segments = sorted(SEGMENT_ROOT.glob("**/sim.csv"))
    if not segments:
        raise SystemExit(f"No sim.csv files found under {SEGMENT_ROOT}")
    segment_path = segments[0]
    print(f"segment: {segment_path}")

    out = plot(segment_path, {"v0": v0}, out_path=OUT_PATH)

    assert out == OUT_PATH, f"plot() returned {out!r}, expected {OUT_PATH!r}"
    assert out.exists(), f"PNG was not written at {out}"
    size = out.stat().st_size
    assert size > 1000, f"PNG suspiciously small: {size} bytes"
    print(f"OK — wrote {out} ({size} bytes)")


if __name__ == "__main__":
    main()
