"""Partition segment sim.csv paths into train and dev lists, grouping by whole route.

A "route" is one recorded drive — identified by the (platform, device, route) tuple
parsed from the path schema:

    data/sim/segments/<PLATFORM>/<DEVICE>/<ROUTE>/<IDX>/sim.csv

Adjacent samples within a single route are highly correlated, so per-segment random
splitting leaks information across the partition. This module assigns whole routes
to one side or the other.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Iterable


def _parse_route_key(path: Path) -> tuple[str, str, str]:
    """Extract (platform, device, route) from a sim.csv path.

    Expects the last 5 parts of the path to be:
        <PLATFORM>/<DEVICE>/<ROUTE>/<IDX>/sim.csv
    """
    parts = path.parts
    if len(parts) < 5 or parts[-1] != "sim.csv":
        raise ValueError(
            f"Path does not match expected schema "
            f"<PLATFORM>/<DEVICE>/<ROUTE>/<IDX>/sim.csv: {path}"
        )
    platform, device, route, _idx, _leaf = parts[-5:]
    return platform, device, route


def _default_glob() -> list[Path]:
    """Default segment glob, resolved against the current working directory.

    Matches ALL platforms (not just FORD_*) — the older default silently
    excluded Hyundai and Tesla, the same cohort bug score-model used to have.
    """
    root = Path.cwd() / "data" / "sim" / "segments"
    return sorted(p for p in root.glob("*/**/sim.csv") if p.is_file())


def _split_one_pool(
    paths: list[Path],
    dev_fraction: float,
    seed: int,
) -> tuple[list[Path], list[Path]]:
    """Greedy whole-route split for a single pool of paths."""
    # Group by (platform, device, route).
    groups: dict[tuple[str, str, str], list[Path]] = {}
    for p in paths:
        key = _parse_route_key(p)
        groups.setdefault(key, []).append(p)

    group_keys = sorted(groups.keys())  # deterministic order before shuffle
    rng = random.Random(seed)
    rng.shuffle(group_keys)

    n_total = len(paths)
    target = dev_fraction * n_total

    dev: list[Path] = []
    train: list[Path] = []
    for key in group_keys:
        members = groups[key]
        if len(dev) < target:
            dev.extend(members)
        else:
            train.extend(members)

    return train, dev


def split(
    segment_paths: Iterable[Path] | None = None,
    dev_fraction: float = 0.25,
    seed: int = 42,
    stratify_by_platform: bool = True,
) -> tuple[list[Path], list[Path]]:
    """Split segment paths into train and dev, holding out whole routes.

    Args:
        segment_paths: iterable of sim.csv paths. If None, globs all
            `data/sim/segments/*/**/sim.csv` (every platform) under the cwd.
        dev_fraction: target fraction of segments in dev. Greedy fill — stops
            on first crossing, so actual fraction may exceed the target slightly.
        seed: RNG seed for the route-group shuffle. Same seed + same inputs ->
            identical split.
        stratify_by_platform: if True, run the split independently per platform
            so each platform contributes ~dev_fraction of its own segments.

    Returns:
        (train_paths, dev_paths) — two disjoint, sorted lists of pathlib.Path.
        Together they cover every input path exactly once.
    """
    if segment_paths is None:
        paths = _default_glob()
    else:
        paths = [Path(p) for p in segment_paths]

    if not paths:
        return [], []

    if stratify_by_platform:
        # Bucket by platform, split each independently.
        by_platform: dict[str, list[Path]] = {}
        for p in paths:
            platform, _device, _route = _parse_route_key(p)
            by_platform.setdefault(platform, []).append(p)

        train: list[Path] = []
        dev: list[Path] = []
        # Deterministic platform iteration, with a derived seed per platform so
        # adding/removing a platform doesn't reshuffle the others.
        for platform in sorted(by_platform.keys()):
            pool_seed = seed ^ (hash(platform) & 0xFFFFFFFF)
            t, d = _split_one_pool(by_platform[platform], dev_fraction, pool_seed)
            train.extend(t)
            dev.extend(d)
    else:
        train, dev = _split_one_pool(paths, dev_fraction, seed)

    train.sort()
    dev.sort()
    return train, dev
