---
name: baseline-residual
description: Compute the V0 baseline residual on a Ford platform with the canonical conventions — right column, right sign, right regime mask, no preprocessing. Returns overall + per-regime RMSE that exactly matches `evals/baseline_rmse.py`. Use this as the first step of the variant ladder.
when-to-load: First step of any lateral-fidelity ladder; before V0 is reported.
inputs: Platform name (`FORD_MUSTANG_MACH_E_MK1` or `FORD_F_150_LIGHTNING_MK1`).
outputs: Dict `{overall, straight, steady, transient}` of RMSE values (rad/s).
load-cost: ~200 tokens metadata, ~400 tokens body.
---

# baseline-residual

## When to load

The first thing the variant ladder needs is a trustworthy V0. This skill produces it. Load before V0 is committed to the report.

## What it computes

Walks every `sim.csv` under `data/sim/segments/<PLATFORM>/`, concatenates, applies the regime mask, and returns RMSE of `yaw_rate_resid_rads` overall and per regime — with **no preprocessing**. Identical numbers to `evals/baseline_rmse.py`; if your computation disagrees, you have a bug.

## Conventions (locked)

- **Scored column.** `yaw_rate_resid_rads` from the CSV as-is.
- **No preprocessing.** No bias removal, no smoothing, no lag alignment. Those belong in V1+.
- **Regime mask** (constant across the whole ladder):
  - `straight`: `|delta_road_rad| < 0.01 rad`
  - `steady cornering`: `|delta_road_rad| ≥ 0.01` ∧ `|d(delta_road_rad)/dt| < 0.05 rad/s`
  - `transient cornering`: `|delta_road_rad| ≥ 0.01` ∧ `|d(delta_road_rad)/dt| ≥ 0.05 rad/s`

## Usage

```bash
python3 skills/baseline-residual/run.py FORD_MUSTANG_MACH_E_MK1
```

Prints overall + per-regime RMSE. Also prints sample counts per regime so you know what the per-regime numbers are computed against.

## Discipline

- **Do not skip this step.** V0 must come from this skill (or the equivalent in `evals/baseline_rmse.py`); a hand-rolled V0 risks fold-in preprocessing.
- **Do not modify** this skill to add preprocessing. The whole point is that V0 is *the residual as the sim run produced it*.
