---
name: make-train-dev-split
description: Split segment sim.csv paths into two disjoint lists — train and dev — holding out whole routes so segments from the same drive stay together. Use this when you want to fit on one slice and check performance on a slice you didn't fit on, to detect overfitting while iterating. Per-segment random splitting would leak information because adjacent samples within a route are highly correlated.
when-to-invoke: You are about to fit / tune a model and want a clean train/dev partition over segment paths, with whole-route grouping enforced. Not for loading the segment data itself — use load-segments for that. Not for scoring — use score-model.
inputs: segment_paths (list[Path] or None), dev_fraction (float, default 0.25), seed (int, default 42), stratify_by_platform (bool, default True).
outputs: tuple (train_paths, dev_paths) — two sorted, disjoint lists of pathlib.Path covering all input paths.
load-cost: ~80 tokens metadata, ~180 tokens body.
---

# make-train-dev-split

## What it does

`split(...)` groups segments by `(platform, device, route)` — a "route" being one recorded drive — then assigns whole groups to either train or dev. Within a group, every segment goes to the same side, so correlated neighbours never straddle the partition.

Algorithm:
1. Group input paths by `(platform, device, route)` parsed from the path: `data/sim/segments/<PLATFORM>/<DEVICE>/<ROUTE>/<IDX>/sim.csv`.
2. Shuffle the groups with `seed`.
3. Greedy-fill dev in shuffle order until cumulative segment count crosses `dev_fraction × n_total`. The remainder goes to train.
4. If `stratify_by_platform=True`, run steps 1–3 independently per platform so each platform contributes roughly `dev_fraction` of its own segments.

Both returned lists are sorted for determinism. Same `seed` + same inputs → identical output.

## What it does not do

- It does not load any segment data. It only partitions paths.
- It does not hit `dev_fraction` exactly — greedy fill, stops on first crossing.
- It does not validate that the paths exist. Garbage in, garbage out.

## Usage

```python
from skills.make_train_dev_split.split import split

train_paths, dev_paths = split(dev_fraction=0.25, seed=42)
print(len(train_paths), len(dev_paths))

# Fit on train, evaluate on dev — see score-model for the latter.
```

Pass an explicit `segment_paths` list to partition a custom subset; pass `None` (default) to glob all `data/sim/segments/FORD_*/**/sim.csv` from the current working directory.

## Smoke test

`python3 _smoke.py` — runs `split()` on the default glob, asserts disjointness, asserts no route appears on both sides, asserts the dev fraction is within ±0.1 of the target, and asserts re-running with the same seed reproduces the same split.

This is a starting point. Modify, extend, or replace as your task demands.
