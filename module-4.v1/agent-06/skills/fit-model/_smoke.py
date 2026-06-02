"""Smoke test for fitting-model.

Fits a 2-param affine V0 correction (`a * yaw_rate_pred_rads + b`) per
platform on a handful of train segments, with the `cte` objective, and
asserts:

- every platform with usable train data converges (or at least returns a
  finite train_obj)
- the fitted train objective is <= V0's train objective (we can only get
  better, never worse, by allowing affine slack — sanity check on the
  optimisation loop)
- a non-None dev_obj is returned when dev_segments is passed

Run standalone: ``python3 _smoke.py``
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fit import fit, format_fit_summary  # noqa: E402


def predict_factory(platform, coeffs):
    a = float(coeffs["a"])
    b = float(coeffs["b"])

    def predict(sim_df):
        return a * sim_df["yaw_rate_pred_rads"].to_numpy(dtype=float) + b

    return predict


def main() -> int:
    seg_root = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/data/sim/segments")
    assert seg_root.exists(), f"sim/segments root not found: {seg_root}"

    train: list[Path] = []
    dev:   list[Path] = []
    platforms: list[str] = []
    for plat_dir in sorted(seg_root.glob("*")):
        if not plat_dir.is_dir():
            continue
        all_paths = sorted(plat_dir.glob("**/sim.csv"))
        if len(all_paths) < 3:
            continue
        platforms.append(plat_dir.name)
        train.extend(all_paths[:3])
        dev.extend(all_paths[3:4])
    assert platforms, "no platforms with enough segments"
    print(f"[smoke] fitting affine V0 correction on {len(train)} train + "
          f"{len(dev)} dev segments across {len(platforms)} platforms: {platforms}")

    init = {plat: {"a": 1.0, "b": 0.0} for plat in platforms}

    # V0 baseline objective on train: fit with a=1.0, b=0.0 fixed.
    v0_result = fit(
        predict_factory, init,
        train_segments=train,
        objective="cte",
        max_iter=1,
        verbose=False,
    )
    # Real fit: free a, b.
    fitted = fit(
        predict_factory, init,
        train_segments=train,
        objective="cte",
        dev_segments=dev,
        max_iter=200,
        verbose=False,
    )

    assert fitted["objective"] == "cte"
    assert fitted["dev_obj"] is not None, "dev_obj must be populated when dev_segments is passed"

    # Each platform with train data must have a finite train_obj and the
    # fitted train_obj must be <= V0's train_obj (affine slack ⇒ never worse).
    any_improved = False
    for plat in platforms:
        tr_v0 = v0_result["train_obj"].get(plat, float("inf"))
        tr_ft = fitted["train_obj"].get(plat, float("inf"))
        assert np.isfinite(tr_ft), f"{plat}: train_obj non-finite ({tr_ft})"
        # tiny tolerance for floating point — fit cannot make things worse than V0.
        assert tr_ft <= tr_v0 + 1e-6, (
            f"{plat}: fitted train_obj {tr_ft:.6f} > V0 train_obj {tr_v0:.6f}"
        )
        if tr_ft < tr_v0 - 1e-6:
            any_improved = True

    assert any_improved, "no platform improved on V0 — optimiser is not searching"

    print("[smoke] PASS")
    print()
    print(format_fit_summary(fitted))
    return 0


if __name__ == "__main__":
    sys.exit(main())
