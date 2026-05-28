---
name: regime-segmentation
description: Tag every row of a Ford `sim.csv` with a driving-regime label (straight / steady-cornering / transient-cornering) using a deterministic mask based on steering angle and steering-rate thresholds. Use whenever a downstream analysis needs per-regime breakdowns or wants to weight cornering samples differently. Composes naturally with lateral-fidelity-triage.
when-to-load: When the task names "per-regime", "regime breakdown", "cornering vs straight", or any time another skill asks for a regime-tagged DataFrame.
inputs: A pandas DataFrame loaded from a Ford `sim.csv`, or a list of CSV paths.
outputs: A DataFrame with an added `regime` column, or a per-regime summary table.
version: 0.3
changelog:
  - v0.1 — initial thresholds (|δ| < 0.01 rad straight; everything else cornering).
  - v0.2 — split cornering into steady vs transient on |dδ/dt| < 0.05 rad/s after the first lateral-fidelity-triage run lumped them.
  - v0.3 — added time-derivative robustness (uniform 50 Hz assumed, but the helper checks dt and falls back to 0.02 s on bad rows).
---

# regime-segmentation

## When to load

Load when a task wants per-regime numbers, or when another skill asks for a regime-tagged DataFrame to feed into its own procedure.

## The procedure (2 steps)

### Step 1 — load and validate

Load one or more Ford `sim.csv` files. Validate that `t_s` and `delta_road_rad` are present. Reject if `t_s` is non-monotone or has gaps > 0.5 s.

Helper: `segment.load_and_validate(csv_paths)`.

### Step 2 — tag

Add a `regime` column with values in `{"straight", "steady", "transient"}`:

- **straight** — `|delta_road_rad| < 0.01 rad`
- **steady cornering** — `|δ| ≥ 0.01 rad` AND `|d δ/dt| < 0.05 rad/s`
- **transient cornering** — `|δ| ≥ 0.01 rad` AND `|d δ/dt| ≥ 0.05 rad/s`

`d δ/dt` is computed from `np.gradient(delta_road_rad) / dt` with `dt` taken from `t_s` per-row, falling back to 0.02 s if a row's dt is non-positive.

Helper: `segment.tag(df) -> df_with_regime`.

## Convenience

`segment.per_regime_rmse(df, resid_col)` returns `{overall, straight, steady, transient}` RMSE values. This is what `lateral-fidelity-triage` calls to populate its variant-ladder columns.

## Composition with lateral-fidelity-triage

The canonical flow is:

```python
import segment            # this skill
import triage             # the other skill

df = segment.load_and_validate(ford_csv_paths)
df = segment.tag(df)
# now df has a `regime` column; pass to triage's ladder
ladder = triage.run_full_ladder(df, platform="FORD_MUSTANG_MACH_E_MK1")
```

Either skill can sit at the top — `regime-segmentation` is a pure dataframe transform, `lateral-fidelity-triage` is the analytical playbook. They share the same regime thresholds (kept in lockstep by convention; the domain expert owns both).

## What this skill deliberately does NOT do

- It does not pick the platform. That's the caller's job.
- It does not compute residuals. Use `lateral-fidelity-triage`'s helpers.
- It does not filter rows out. Use the `regime` column to slice downstream.
