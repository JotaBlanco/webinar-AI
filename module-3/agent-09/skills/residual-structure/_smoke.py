"""Smoke test for residual-structure.

Two scenarios:
  1. V0 passthrough across all platforms — Ford/Hyundai residuals are heavily
     structured (V0 has no understeer at all), so the verdict should be
     `structure_detected` on each, and the dashboard should mention either
     ACF or a feature derivative. Tesla's truth IS V0, so verdict is `noise_floor`.
  2. A deliberately-noisy passthrough (V0 + iid gaussian noise) on one platform
     — residual is white noise → verdict should be `noise_floor`.

Run standalone: ``python3 _smoke.py``
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from residual_structure import (  # noqa: E402
    format_residual_structure_summary,
    residual_structure,
)


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
        seg_paths.extend(sorted(plat_dir.glob("**/sim.csv"))[:4])
    assert seg_paths, f"no sim.csv under {seg_root}"

    print(f"[smoke] residual-structure on {len(seg_paths)} segments / "
          f"{len(platforms_on_disk)} platforms: {platforms_on_disk}")

    # --- Scenario 1: V0 passthrough — Fords/Hyundai should be structured.
    result = residual_structure(v0, segment_paths=seg_paths)
    per_plat = result["per_platform"]

    for plat in platforms_on_disk:
        assert plat in per_plat, f"residual-structure dropped {plat!r}"

    for plat, m in per_plat.items():
        if "TESLA" in plat:
            # Tesla truth IS V0 — residual is zero, verdict must be noise_floor.
            assert m["verdict"] == "noise_floor", (
                f"{plat}: expected noise_floor on Tesla V0 passthrough, got {m['verdict']!r} ({m['verdict_reason']})"
            )
        else:
            assert m["verdict"] == "structure_detected", (
                f"{plat}: V0 has no understeer — expected structure_detected, "
                f"got {m['verdict']!r} ({m['verdict_reason']})"
            )

    # --- Scenario 2: pure-noise predictor on one platform — must verdict noise_floor.
    rng = np.random.default_rng(0)

    def truth_plus_noise(sim_df, platform):
        # Read the SAME truth column the scorer reads (the agent view aliases
        # baseline to yaw_rate_pred_rads, but the residual = pred - truth, so
        # we want pred = truth + iid noise. We approximate truth by V0 here,
        # which is fine because in the no-noise direction we'd already be at
        # noise_floor; adding gaussian noise on top of it must still be).
        n = len(sim_df)
        yr = sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        # Add iid noise — much larger than any structure, so dominates.
        yr = yr + rng.normal(scale=0.05, size=n)
        return pd.DataFrame({"yaw_rate_pred_rads": yr}, index=sim_df.index)

    # Use Tesla — its V0 residual is zero, so pred − truth = pure noise.
    tesla_paths = [p for p in seg_paths if "TESLA" in str(p)]
    if tesla_paths:
        noisy = residual_structure(truth_plus_noise, segment_paths=tesla_paths)
        plat = next(iter(noisy["per_platform"]))
        m = noisy["per_platform"][plat]
        assert m["verdict"] == "noise_floor", (
            f"pure-noise test: expected noise_floor on Tesla, got {m['verdict']!r} ({m['verdict_reason']})"
        )

    print("[smoke] PASS")
    print()
    print(format_residual_structure_summary(result, top_n_features=4))
    return 0


if __name__ == "__main__":
    sys.exit(main())
