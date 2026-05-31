"""Smoke test for compare-models.

Run directly: `python3 _smoke.py`. Cheap, loud, no fixtures required beyond
the segment data already present in the working tree.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# Make the skill importable when run standalone.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from compare import compare  # noqa: E402


def fn_a(sim_df, platform):
    """V0 baseline — re-use the prediction already in sim.csv."""
    return sim_df[["yaw_rate_pred_rads"]].copy()


def fn_b(sim_df, platform):
    """V0 scaled by 10% — should be slightly worse on average."""
    out = sim_df[["yaw_rate_pred_rads"]].copy()
    out["yaw_rate_pred_rads"] = out["yaw_rate_pred_rads"] * 1.1
    return out


def _pick_segments(n: int = 20) -> list[Path]:
    # Look in the working dir first (where the agent runs); fall back to the
    # repo's top-level data tree if we're invoked from elsewhere.
    candidates = []
    candidates.extend(sorted(Path.cwd().glob("data/sim-full/FORD_MUSTANG_MACH_E_MK1/**/sim.csv")))
    if not candidates:
        repo_data = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/data/sim-full/FORD_MUSTANG_MACH_E_MK1")
        candidates = sorted(repo_data.glob("**/sim.csv"))
    if not candidates:
        raise RuntimeError(
            "Smoke test could not find any FORD_MUSTANG_MACH_E_MK1 sim.csv files. "
            "Run from a working dir that has data/ populated."
        )
    return candidates[:n]


def main() -> int:
    # Use a wider sample so the average direction is visible — many MUSTANG
    # segments are nearly straight, where scaling yaw-rate barely matters.
    segs = _pick_segments(n=20)
    print(f"Comparing on {len(segs)} segments…")
    df = compare(fn_a, fn_b, segment_paths=segs, name_a="v0", name_b="v0_scaled")

    expected_cols = {
        "segment_path", "platform", "n_samples",
        "yaw_rate_rmse_v0", "yaw_rate_rmse_v0_scaled", "yaw_rate_delta",
        "cte_rmse_v0", "cte_rmse_v0_scaled", "cte_delta",
        "frac_straight", "frac_steady", "frac_transient",
    }
    missing = expected_cols - set(df.columns)
    assert not missing, f"missing columns: {sorted(missing)}"
    assert len(df) > 0, "compare() returned an empty DataFrame"

    # The scaled predictor should be worse on average.
    scaled_worse_count = int((df["yaw_rate_delta"] > 0).sum())
    median_delta = float(df["yaw_rate_delta"].median())
    print(f"\nScaled predictor worse on {scaled_worse_count}/{len(df)} segments "
          f"(yaw-rate-delta median = {median_delta:+.6f} rad/s)")

    assert scaled_worse_count >= len(df) / 2, (
        f"expected scaled predictor to be worse on >= half of segments; "
        f"got {scaled_worse_count}/{len(df)}"
    )
    assert median_delta > 0, (
        f"expected median yaw_rate_delta > 0 (scaled worse); got {median_delta}"
    )

    # Show the table so a human can sanity-check.
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 20)
    print("\nHead of compare() result:")
    print(df.head().to_string(index=False))

    print("\nSmoke test PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
