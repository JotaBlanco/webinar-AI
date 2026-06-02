---
name: held-out-split
description: The frozen route-grouped train/dev/test split for module-4.v2.01. Every candidate uses the same partition. Iterate on dev; never touch test until preflight --final. Documents why the split exists and how to use it.
when-to-load: Once at start, before fitting anything. Re-load if you're confused about which paths a skill is reading.
load-cost: ~250 words.
---

# Frozen train/dev/test split

## TL;DR

```python
from _shared.frozen_split import train_paths, dev_paths
train = train_paths()   # 1187 segments — fit on these
dev   = dev_paths()     #  402 segments — evaluate / select on these
# test is reserved — only pre-flight-final-model --final touches it
```

`python _shared/frozen_split.py --summary` prints the partition breakdown.

## Why this is frozen

The m4.v2 cohort (10 agents) had no committed split. Every agent re-split
from scratch with different seeds and fractions; cross-agent comparisons
were apples-to-oranges. **agent-10 (m4.v2)** shipped without a held-out
check at all because "there is no cohort dev/test split frozen for me in
a way I could trust."

v2.01 fixes this. The split is:

- **Route-grouped** — whole drives stay together. Per-sample random
  splits leak because consecutive samples within a route are highly
  correlated. Reuses `skills/make-train-dev-split` under the hood.
- **Platform-stratified** — each of F150 / Mach-E / Ioniq / Tesla appears
  in train, dev, and test in the same fractions.
- **Deterministic** — the seed is `20260603` for test, `20260604` for
  the train/dev partition of the remainder. Re-running gives bit-identical
  paths. (v2.01 also patched a pre-existing `make-train-dev-split` bug
  where `hash(platform)` was per-process-random; the per-platform pool
  seed now uses `zlib.crc32` for stability across runs.)
- **Fractions** — 60 % train / 20 % dev / 20 % test.

| platform | train | dev | test |
|---|---:|---:|---:|
| FORD_F_150_LIGHTNING_MK1 | 103 |  36 |  36 |
| FORD_MUSTANG_MACH_E_MK1  | 142 |  50 |  48 |
| HYUNDAI_IONIQ_5          | 476 | 160 | 164 |
| TESLA_MODEL_3            | 466 | 156 | 159 |

(Tesla has no truth — it scores via passthrough; its split exists for
parity but yields no signal.)

## How to use

- **Fitting** — `fit-model` reads `train_paths()`. The five prefilled
  candidates' `fit.py` scripts already do this.
- **Selection** — `score-model` and `iterate` read `dev_paths()`. Pick
  whichever model wins on dev pooled-yaw + dev pooled-CTE.
- **Final** — `pre-flight-final-model --final` is the only invocation
  allowed to read `test_paths()`. It sets `FROZEN_SPLIT_ALLOW_TEST=1` in
  its env and reports the train→dev→test progression so you can see if
  you over-fit to dev.

## Failure modes

- **You import `test_paths()` outside preflight** → `PermissionError`.
  This is intentional. If you need the count for a sanity check, run
  `python _shared/frozen_split.py --summary` from the shell.
- **`data/` symlink broken** → `_all_paths()` returns empty, raises
  `RuntimeError`. Repair the symlink at the template root.

## What's "honest" about this split

The split is not adversarial. It is the *minimum* discipline that makes
candidates comparable. The harder questions — does this dataset reflect
the operational domain, does the route-grouping leak through shared
hardware, does platform stratification mask a per-platform model bug —
are not solved by holding out 20 %. The split is a floor, not a ceiling.
