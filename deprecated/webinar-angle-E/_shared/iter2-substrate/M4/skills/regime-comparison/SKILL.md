---
name: regime-comparison
description: For a set of (variant-name, residual-series) pairs over the same Ford-segment DataFrame, produce a per-regime contrast table — which variant most affects which regime, with directional sign. Use as an attribution diagnostic after running a variant ladder; complements yaw-divergence-triage by showing where each variant earned (or lost) its delta.
when-to-load: When the task asks "which variant most improves which regime", or when the user wants per-regime attribution beyond the headline RMSE.
inputs: A regime-tagged DataFrame and a dict of {variant_name: residual_array}.
outputs: A small markdown sub-table or a DataFrame; intermediate per-regime numbers.
version: 1.0
---

# regime-comparison

## When to load

Load after a variant ladder has been computed and you want to see *where* each variant's delta concentrated. Pure diagnostic — does not produce a new variant.

## The procedure (1 step)

For each (variant_name, residual_array) pair:

- Tag samples by regime (straight / steady / transient).
- Compute per-regime RMSE.
- Compute per-regime *signed* delta relative to V0.

Return a table:

```
| variant | Δ straight | Δ steady | Δ transient | dominant regime |
```

`dominant regime` is the regime where the variant's |delta| is largest. Negative deltas (RMSE went up) are reported as regressions.

Helper: `compare.contrast(df, variant_residuals, baseline_name="V0")`.

## Reporting

This skill does not write `REPORT.md` itself. The caller embeds the contrast table as a sub-section under "Attribution" in the parent skill's REPORT.md.

## Known trap

If the regime mask is computed differently between this skill and the parent skill, the numbers in this skill's table will not reconcile with the parent's variant ladder. Use the *same* regime column on the *same* DataFrame.
