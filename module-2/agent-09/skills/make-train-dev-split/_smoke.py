"""Smoke test for make-train-dev-split.

Runnable standalone:

    python3 _smoke.py

Verifies:
  - train and dev lists are disjoint (no path appears in both)
  - no (platform, device, route) tuple straddles train and dev
  - actual dev fraction is within +/- 0.1 of the requested fraction
  - re-running with the same seed produces an identical split
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the sibling split.py importable when run standalone.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from split import _parse_route_key, split  # noqa: E402
from validate_split import format_findings, validate_split  # noqa: E402


def main() -> None:
    dev_fraction = 0.25
    seed = 42

    train, dev = split(dev_fraction=dev_fraction, seed=seed)

    n_train = len(train)
    n_dev = len(dev)
    n_total = n_train + n_dev

    if n_total == 0:
        raise SystemExit(
            "Smoke test found zero segments — check that data/sim-full/FORD_* "
            "exists under the current working directory."
        )

    # 1. Disjoint at the path level.
    overlap = set(train) & set(dev)
    assert not overlap, f"train/dev overlap: {len(overlap)} shared paths"

    # 2. Disjoint at the route level — the key invariant.
    train_routes = {_parse_route_key(p) for p in train}
    dev_routes = {_parse_route_key(p) for p in dev}
    route_overlap = train_routes & dev_routes
    assert not route_overlap, (
        f"route leak: {len(route_overlap)} routes appear on both sides — "
        f"example: {next(iter(route_overlap))}"
    )

    # 3. Dev fraction within tolerance.
    actual = n_dev / n_total
    assert abs(actual - dev_fraction) <= 0.1, (
        f"dev fraction {actual:.3f} is more than 0.1 off target {dev_fraction}"
    )

    # 4. Reproducibility.
    train2, dev2 = split(dev_fraction=dev_fraction, seed=seed)
    assert train == train2 and dev == dev2, "same seed produced a different split"

    # 5. Different seed should usually produce a different split (sanity, not strict).
    _t3, dev3 = split(dev_fraction=dev_fraction, seed=seed + 1)
    different = set(dev) != set(dev3)

    print(f"n_train            = {n_train}")
    print(f"n_dev              = {n_dev}")
    print(f"n_total            = {n_total}")
    print(f"dev_fraction_target= {dev_fraction}")
    print(f"dev_fraction_actual= {actual:.4f}")
    print(f"n_routes_train     = {len(train_routes)}")
    print(f"n_routes_dev       = {len(dev_routes)}")
    print(f"reseed_changes_dev = {different}")

    # 6. validate_split should pass with no hard violations.
    findings = validate_split(train, dev, target_dev_fraction=dev_fraction)
    assert not findings["hard_violations"], findings["hard_violations"]
    print()
    print(format_findings(findings))

    # 7. validate_split should raise when fed a deliberately bad split.
    bad_train = list(train) + [dev[0]]  # duplicate path across sides
    try:
        validate_split(bad_train, dev, target_dev_fraction=dev_fraction)
    except ValueError as e:
        print(f"\n(expected) validate_split raised on bad input: {e!s}".splitlines()[0])
    else:
        raise AssertionError("validate_split did not raise on a known-bad split")

    print("\nOK")


if __name__ == "__main__":
    main()
