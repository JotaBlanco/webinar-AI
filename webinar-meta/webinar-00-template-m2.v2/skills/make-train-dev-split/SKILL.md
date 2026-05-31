---
name: making-train-dev-split
description: Split segment sim.csv paths into two disjoint lists — train and dev — holding out whole routes so segments from the same drive stay together. Ships with a `validate_split` helper that checks for route leakage, path collisions, and per-platform imbalance, raising on hard violations. Use this when you want to fit on one slice and check performance on a slice you didn't fit on. Per-segment random splitting would leak information because adjacent samples within a route are highly correlated.
when-to-invoke: You are about to fit / tune a model and want a clean train/dev partition over segment paths with whole-route grouping enforced. After splitting, call `validate_split` to confirm the partition is honest before training against it.
when-NOT-to-invoke: You are not iterating (e.g. final-model run on the full set — just pass all paths to scoring-model). You need a totally custom split policy (write it inline rather than fighting the defaults — the algorithm is 60 lines).
inputs:
  - `split`: segment_paths (list[Path] or None), dev_fraction (float, default 0.25), seed (int, default 42), stratify_by_platform (bool, default True).
  - `validate_split`: train_paths, dev_paths, target_dev_fraction (float or None), raise_on_hard (bool, default True).
outputs:
  - `split(...)` -> tuple (train_paths, dev_paths) — two sorted, disjoint lists of pathlib.Path.
  - `validate_split(...)` -> dict with n_train, n_dev, dev_fraction, route_leaks, path_collisions, per_platform, warnings, hard_violations. Raises ValueError on hard violations by default.
  - `format_findings(findings)` -> markdown string for printing.
load-cost: ~110 tokens metadata, ~250 tokens body.
---

# making-train-dev-split

## What it does

`split(...)` groups segments by `(platform, device, route)` — a "route" being one recorded drive — then assigns whole groups to either train or dev. Within a group, every segment goes to the same side, so correlated neighbours never straddle the partition.

`validate_split(train, dev, target_dev_fraction=...)` is the matching sensor:

- **Raises on hard violations**: route leakage (any route on both sides), path collisions, duplicates within a list.
- **Returns warnings**: dev fraction far from target, a platform with zero segments on one side, severely imbalanced platforms.

Split algorithm:
1. Group input paths by `(platform, device, route)` parsed from `data/sim/segments/<PLATFORM>/<DEVICE>/<ROUTE>/<IDX>/sim.csv`.
2. Shuffle the groups with `seed`.
3. Greedy-fill dev in shuffle order until cumulative segment count crosses `dev_fraction × n_total`. Remainder goes to train.
4. If `stratify_by_platform=True`, run steps 1–3 independently per platform.

Both returned lists are sorted for determinism. Same `seed` + same inputs → identical output.

## What it does not do

- Does not load any segment data. It only partitions paths.
- Does not hit `dev_fraction` exactly — greedy fill, stops on first crossing.
- Does not validate that the paths exist on disk.

## Usage

```python
from skills.make_train_dev_split.split import split
from skills.make_train_dev_split.validate_split import validate_split, format_findings

train, dev = split(dev_fraction=0.25, seed=42)
findings = validate_split(train, dev, target_dev_fraction=0.25)
print(format_findings(findings))
```

If you do not want the hard-violation check to raise (e.g. while debugging a custom split), pass `raise_on_hard=False` and inspect `findings["hard_violations"]` directly.

## Smoke test

`python3 _smoke.py` — runs `split()` on the default glob, asserts disjointness, asserts no route appears on both sides, asserts the dev fraction is within ±0.1 of target, asserts re-running with the same seed reproduces the split. Then runs `validate_split` and confirms no hard violations.

## Extending this skill

If you want a different leakage unit (e.g. group by `device` instead of `route`), edit `_parse_route_key` in both files. If you want a different fill policy (e.g. fill to target then balance), `split.py` is short enough to rewrite inline.
