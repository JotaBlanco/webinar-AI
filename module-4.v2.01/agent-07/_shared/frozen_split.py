"""Frozen route-grouped train/dev/test split for module-4.v2.01.

Why this exists
---------------
The m4.v2 cohort had no committed split. Every agent re-split from scratch.
Agent-10 (m4.v2) explicitly cited "no cohort dev/test split frozen in a way
I could trust without reading prior cohort outputs" as the reason they
shipped without a held-out check.

This module wraps `skills/make-train-dev-split` with a frozen seed and
fixed fractions so every candidate in this template gets the same
partition. The split is route-grouped (no leakage), platform-stratified,
and deterministic across runs.

Partition
---------
- **test** — 20% of routes (frozen). Touch only at preflight `--final`.
- **dev**  — 20% of routes from the remainder. CV evaluation, model
  selection.
- **train** — 60% of routes. Coefficient fits, structure exploration.

Usage
-----
    from _shared.frozen_split import train_paths, dev_paths, test_paths
    train = train_paths()  # list[pathlib.Path] to sim.csv files
    dev   = dev_paths()
    test  = test_paths()   # raises if called outside preflight --final

To inspect the partition without loading data:
    python _shared/frozen_split.py --summary
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent / "skills" / "make-train-dev-split"
sys.path.insert(0, str(SKILL_DIR))
from split import split as _split_routes  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
SEGMENTS_ROOT = REPO_ROOT / "data" / "sim" / "segments"

# Frozen — do not change without a cohort-wide regrade.
TEST_SEED = 20260603
TEST_FRACTION = 0.20
DEV_SEED = 20260604
DEV_FRACTION_OF_REMAINDER = 0.25  # → 20% of total


def _all_paths() -> list[Path]:
    return sorted(SEGMENTS_ROOT.glob("*/*/*/*/sim.csv"))


def _three_way() -> tuple[list[Path], list[Path], list[Path]]:
    """Return (train, dev, test) deterministically."""
    all_paths = _all_paths()
    if not all_paths:
        raise RuntimeError(
            f"No sim.csv files under {SEGMENTS_ROOT}. Is the data/ symlink intact?"
        )
    remainder, test = _split_routes(
        all_paths,
        dev_fraction=TEST_FRACTION,
        seed=TEST_SEED,
        stratify_by_platform=True,
    )
    train, dev = _split_routes(
        remainder,
        dev_fraction=DEV_FRACTION_OF_REMAINDER,
        seed=DEV_SEED,
        stratify_by_platform=True,
    )
    return train, dev, test


def train_paths() -> list[Path]:
    return _three_way()[0]


def dev_paths() -> list[Path]:
    return _three_way()[1]


def test_paths() -> list[Path]:
    """Held-out test. Refused outside preflight --final unless FROZEN_SPLIT_ALLOW_TEST is set."""
    if os.environ.get("FROZEN_SPLIT_ALLOW_TEST") != "1":
        raise PermissionError(
            "test_paths() is reserved for pre-flight-final-model --final. "
            "Use dev_paths() during iteration. If you really mean it, set "
            "FROZEN_SPLIT_ALLOW_TEST=1 in the env."
        )
    return _three_way()[2]


def _summarise() -> None:
    train, dev, test = _three_way()
    by_platform = {}
    for label, paths in [("train", train), ("dev", dev), ("test", test)]:
        for p in paths:
            plat = p.parts[-5]
            by_platform.setdefault(plat, {"train": 0, "dev": 0, "test": 0})
            by_platform[plat][label] += 1
    print(f"Total segments: {len(train) + len(dev) + len(test)}")
    print(f"  train: {len(train)}   dev: {len(dev)}   test: {len(test)}")
    print()
    print(f"{'platform':<32} {'train':>6} {'dev':>6} {'test':>6}")
    for plat in sorted(by_platform):
        c = by_platform[plat]
        print(f"{plat:<32} {c['train']:>6} {c['dev']:>6} {c['test']:>6}")


if __name__ == "__main__":
    if "--summary" in sys.argv:
        _summarise()
    else:
        print("Usage: python _shared/frozen_split.py --summary")
