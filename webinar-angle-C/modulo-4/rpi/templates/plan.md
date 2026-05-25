# Plan — improvements to evaluate

> Fill end-to-end before writing any code. Goal: pick 1-2 improvements with a falsifiable success criterion and a pre-committed ablation table.

## Candidate improvements (≥3)

For each candidate:

### Candidate A — <name>
- **Hypothesis (physical):** <why this should reduce the residual>
- **Signal that suggests it:** <what in research.md points here>
- **How to implement:** <files to copy from `code/` into `out/`, lines to change>
- **Expected effect:** <direction + rough magnitude>
- **Falsification:** <what would prove this is the wrong fix>

### Candidate B — <name>
...

### Candidate C — <name>
...

## Selected for implementation (1-2)

- <candidate X> — because <reason>.
- <candidate Y, if any>.

## Pre-committed ablation table

Fill in the **method** column now; numbers come later.

| Variant | Method | Expected RMSE ψ̇ (°/s) | Actual | Δ |
|---|---|---|---|---|
| baseline | as-is | | | — |
| + cand X | <how> | | | |
| + cand X + cand Y | <how> | | | |

## Success criterion (lock this)

- Numerical: <e.g. "RMSE ψ̇ drops ≥ 15% on both platforms, no platform gets worse">
- Physical: <e.g. "the residual is no longer monotone in |a_y|">

## What this plan deliberately does NOT do

- <e.g. "no full Pacejka tyre — too expensive for time budget">
- <e.g. "no re-decode of CAN — assume adapter outputs are correct">
