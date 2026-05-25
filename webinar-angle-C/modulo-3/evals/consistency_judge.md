# Inferential sensor — REPORT.md consistency judge

> An LLM-as-judge spec. Cheap, opinionated, run last. Computational sensors (schema, RMSE recompute) run first; the judge is for what a deterministic check cannot see.

## Inputs
- The agent's `REPORT.md`.
- The agent's `rpi/runs/<timestamp>/plan.md` (the locked plan).
- The output of `evals/baseline_rmse.py` (ground truth for baseline numbers).

## The judge's checklist

Score 0–2 on each. 0 = absent/wrong, 1 = partial, 2 = correct.

1. **Baseline numbers match `baseline_rmse.py` output** within ±0.05 °/s per platform.
2. **Each implemented improvement traces to a candidate listed in `plan.md`** (or the plan was explicitly amended with reason).
3. **Ablation table** has one row per variant (baseline → +X → +X+Y), and the Δ column is computed correctly.
4. **Ranking of impact** distinguishes "did improve" from "did not improve" and reports both.
5. **Limitations section** names ≥1 thing the agent could not check given its harness components (this is the angle-C-specific test).

## Pass threshold

Total ≥ 8/10. A failure on item 1 is always a fail regardless of total.

## Usage

The judge is invoked manually by the workshop facilitator. Prompt template:

> You are evaluating a workshop participant's `REPORT.md` against the checklist below. Read the report and the plan. Score each item 0-2, with a one-line justification. Output as a markdown table, followed by the total and pass/fail.
