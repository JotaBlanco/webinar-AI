---
name: ablation-study
description: Run a controlled ablation over model variants. Each variant adds exactly one change on top of the previous; the table reports per-platform RMSE delta. Load this skill when the task asks "quantify the contribution of each change".
when_to_use: After you have ≥2 candidate improvements and need to attribute fidelity gain to specific changes. Use *after* baseline-residual.
inputs: A list of variants. Each variant = `(name, code-path)` where the code-path produces a directory of Ford CSVs in the same schema as `data/sim/`.
outputs: `ablation.csv` (one row per variant × platform), and a markdown table for REPORT.md.
---

# Ablation study — recipe

## The shape

A valid ablation is *additive and monotone*:
- baseline (unchanged code)
- baseline + change_A
- baseline + change_A + change_B
- ...

Do **not** mix two changes in one variant unless they are intrinsically coupled — you'll lose attribution.

## The procedure

1. For each variant, generate Ford CSVs in a dedicated dir under `out/sim_<variant_name>/`.
2. Run `evals/schema_check.py out/sim_<variant_name>/` — if it fails, the variant is invalid and **does not enter the ablation**. Fix the variant or drop it.
3. Run `python skills/ablation-study/run.py out/sim_baseline/ out/sim_+A/ out/sim_+A+B/ ...` (or call programmatically).
4. The output is a table with columns: `variant`, `platform`, `RMSE_yaw_degs`, `Δ_vs_baseline_abs`, `Δ_vs_baseline_pct`.

## REPORT.md format

```
| Variant | Mach-E RMSE ψ̇ (°/s) | Δ abs | Δ % | F-150 RMSE ψ̇ (°/s) | Δ abs | Δ % |
|---|---|---|---|---|---|---|
| baseline | X.XX | — | — | X.XX | — | — |
| + change_A | X.XX | -Y.YY | -ZZ% | ... |
| + change_A + change_B | ... |
```

## Gotchas

- If `change_A` makes one platform better and the other worse, *report both* — do not silently drop the worse one.
- Δ % is computed against the **baseline**, not the previous row.
- If the schema check fails for a variant, that variant is excluded with an explicit "schema_check failed: <reason>" note. Honesty over numbers.
