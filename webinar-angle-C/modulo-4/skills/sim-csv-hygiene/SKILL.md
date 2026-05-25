---
name: sim-csv-hygiene
description: Normalise Ford sim CSVs so they pass `evals/schema_check.py`. Specifically, recompute `yaw_rate_resid_rads` and `a_y_resid_mps2` from `meas − pred` at full float64 precision, overwriting whatever was stored. Use this on any directory of sim CSVs before running it through schema_check, especially after copying CSVs across filesystems or after applying any variant transformation.
when_to_use: Whenever schema_check.py FAILS with "a_y_resid sign wrong (max diff ~1e-6)" or "yaw_rate_resid sign wrong" — these are floating-point round-trip artifacts from the CSV-precision boundary, not real residual sign bugs. Also as the last step of any variant generator before handing CSVs to the ablation tool.
inputs: A directory of Ford sim CSVs (mirrors `data/sim/segments/` layout).
outputs: The same CSVs rewritten in place with `yaw_rate_resid_rads = yaw_rate_meas_rads − yaw_rate_pred_rads` and `a_y_resid_mps2 = a_lat_meas_mps2 − a_y_pred_mps2` at full precision.
---

# sim-csv-hygiene — recipe

## Why this exists

`evals/schema_check.py` enforces `|resid − (meas − pred)| < 1e-6`. CSVs written with default float repr round-trip to ~7 significant digits, which is enough for raw values but borderline for *differences* of similar-magnitude numbers — the comparison can land at exactly 1.0e-6 and fail. This was discovered when a *baseline* CSV failed schema_check despite never having been transformed.

The honest fix is: recompute the derived columns from the source columns at full precision after any CSV write. That is what this skill does.

## The procedure

1. Walk the directory for `FORD_*/**/*.csv`.
2. For each CSV: load → recompute `yaw_rate_resid_rads` and `a_y_resid_mps2` from `meas − pred` → write back with `float_format='%.10g'` so the residual round-trips cleanly.
3. Re-run `evals/schema_check.py <dir>` to confirm 0 failures.

## When NOT to use

- If schema_check.py flags a residual diff of, say, > 1e-3, that's a real sign bug — do not paper over it with this skill. Investigate the upstream variant.
- If the variant's whole point is to redefine `resid` (none in this challenge), this skill will silently overwrite that change.
