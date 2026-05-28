# Judge prompt template — graded by `grade-cohort-reports`

> Placeholders in `{{double-braces}}`. `prepare.py` fills them per report.

---

You are a strict-but-fair grader for a workshop experiment. You will read **one agent's report** and score it against a fixed rubric authored by the workshop's domain expert.

## Grading principles

- **Generous on paraphrase.** If the agent meets the spirit of a rubric item — even using different terminology — credit it. Workshop reports vary in style; we are scoring substance.
- **Strict on evidence.** Every PASS verdict must include at least one **verbatim quote** from the report that justifies it. No quote → FAIL. This is the audit trail; there is no "I just feel this report is good."
- **No halo effect.** Score each rubric item independently. A strong report on items 1-3 does not give item 4 the benefit of the doubt.
- **Read carefully on definitions.** If a rubric item asks for evidence of a *measured* channel, a fabricated proxy, derived signal, or clamped channel does **not** count. Note such cases as FAIL with the agent's own words showing the fabrication.
- **`null` is a legitimate result.** If the report neither passes nor fails because the item simply isn't addressed, return `result: null` with `reasoning: "not addressed in report"`. Don't guess.

## The rubric — score against this and only this

This is from `webinar-00/domain-knowledge-challenges/idea-01-lateral-attribution.md`. The YAML metadata is the canonical rubric.

```yaml
title: Idea 01 — Lateral attribution
slug: idea-01-lateral-attribution
domain: vehicle-dynamics
tests:
  - attribution-discipline
  - regime-segmentation
  - operating-contract
  - metric-selection
  - truth-channel-discovery
best-fit-angles: [01-accretion, 04-author, 05-experiment]
weak-fit-angles: [02-empathy, 03-harness-as-product]
success-metrics:
  - id: truth-channel-correct
    type: binary
    rubric: the report scores against a measured channel, not a clamped or self-predicted one
    evidence-in-report: report names the scored channel and identifies it as measured, citing the dataset/source
  - id: contract-acknowledged
    type: binary
    rubric: the report states which channels are clamped to truth vs predicted by the model
    evidence-in-report: an explicit clamped-vs-predicted statement in the methodology section
  - id: regime-breakdown-present
    type: binary
    rubric: the report breaks out error by regime (straight / cornering / transient), not only an aggregate
    evidence-in-report: a per-regime table or chart of the chosen metric
  - id: methodology-consistent
    type: binary
    rubric: same segment list and same metric definition across every variant on the ladder
    evidence-in-report: variant table shares a fixed segment-set / regime-mask declaration in its header or caption
  - id: attribution-coherent
    type: numeric
    rubric: "|Σ marginal RMSE drops − total drop| / total drop (no double-counting)"
    threshold: "< 0.15"
    evidence-in-report: marginal-RMSE column and total-drop value both present and reconcilable
  - id: honest-regression-flagged
    type: binary
    rubric: any variant that worsened the metric is reported as a regression with a physical reason; vacuous if no regression occurred
    evidence-in-report: variant table includes regression rows with a physical-cause column, OR an explicit "no regressions observed" statement
naked-prompt-audit:
  metric-named: false
  platform-named: false
  contract-named: false
  catalogue-suggested: false
  scoring-procedure-suggested: false
```

For each item in `success-metrics`, decide PASS/FAIL/NULL and quote your evidence. For `type: numeric` items, also estimate the value the report implies and check it against the `threshold` (the rubric specifies what direction is good).

## The report — score this one only

- agent_id: **angleC-m4-agent-05**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-4/agent-05/REPORT.md`

```markdown
# Module-4 / agent-05 (angle-C) — Lateral-fidelity challenge

## Headline

KS lateral predictions improved on both Ford platforms via an additive monotone ladder fit per-platform on an interleaved 5th-sample test split. **The dominant model-improvement DOF is a per-platform steering-gain scale `k`, and it has opposite signs on the two platforms** — Mach-E wants k=1.095 (KS under-predicts), F-150 Lightning wants k=0.867 (KS over-predicts). Per-segment bias is reported separately and labelled calibration, not model improvement.

Platforms: FORD_MUSTANG_MACH_E_MK1 (315 segments / 913 626 samples), FORD_F_150_LIGHTNING_MK1 (230 / 667 141). Truth = `yaw_rate_meas_rads`, `a_lat_meas_mps2` (Ford only). Operating contract: KS lateral-only, `v` and `δ` clamped, only ψ, ψ̇, a_y, x, y predicted. Score column: ψ̇ residual recomputed as `pred − meas`.

## Variants (interleaved split, additive, locked order, per-platform fit)

**Mach-E:**

| Variant | DOF | Overall | Straight | Steady | Transient | Marg Δ |
|---|---|---|---|---|---|---|
| V0 baseline | 0 | 0.01613 | 0.00878 | 0.03147 | 0.05743 | — |
| V1 bias (b=+0.00023) | 1 plat | 0.01613 | 0.00876 | 0.03149 | 0.05745 | -0.00000 |
| V2 gain (k=1.0948) | 1 plat | 0.01566 | 0.00979* | 0.02968 | 0.05022 | -0.00047 |
| V3 lag (n=3, 60 ms) | 1 plat | 0.01541 | 0.00967 | 0.02966 | 0.04785 | -0.00025 |
| V4 per-seg bias (cal) | ~315 seg | 0.01323 | 0.00646 | 0.02797 | 0.04483 | -0.00219 |

**F-150 Lightning:**

| Variant | DOF | Overall | Straight | Steady | Transient | Marg Δ |
|---|---|---|---|---|---|---|
| V0 baseline | 0 | 0.02037 | 0.00899 | 0.03629 | 0.05161 | — |
| V1 bias (b=+0.00363) | 1 plat | 0.02005 | 0.00800 | 0.03629 | 0.05158 | -0.00033 |
| V2 gain (k=0.8672) | 1 plat | 0.01637 | 0.00645 | 0.02866 | 0.04474 | -0.00368 |
| V3 lag (n=3, 60 ms) | 1 plat | 0.01614 | 0.00631 | 0.02863 | 0.04336 | -0.00023 |
| V4 per-seg bias (cal) | ~230 seg | 0.01488 | 0.00598 | 0.02647 | 0.03940 | -0.00126 |

Attribution coherence = 0.0000 on both. `*` Regression: Mach-E V2 raises straight RMSE 0.00878→0.00979 — gain >1 amplifies near-zero straight noise; net overall still a win; kept in ladder per `ablation-study` discipline.

## Painful absence

`evals/schema_check.py` **FAILS** on the canonical baseline CSVs (`max diff 1.32e-01`): the stored `yaw_rate_resid_rads` is `meas − pred`, not `pred − meas` as ratchet item #1 declares. RMSE-blind so V0 numbers are unaffected, but any signed downstream analytic would silently invert. **This is exactly the ratchet-#1 past failure sitting in the production data.** My ladder bypasses by recomputing residual from `pred − meas`; producer (`code/generate_simdata_ford.py`) needs fixing.

## Near-misses

- V1 bias on Mach-E ≈ noise (+0.00023). No constant zero-offset on that platform. F-150 has a real +0.00363 (truck IMU thermal offset is the likely physical cause).
- V3 lag scan independently picked n=3 (60 ms) on **both** platforms from [0,10]-sample range — consistent with openpilot CAN latency + small tyre relaxation.

## Surprise

Gain sign flips between platforms. Same kinematic model, opposite mismatches: Lightning's higher mass + longer wheelbase + truck tyres heavily slip-damp ψ̇ vs the kinematic prior; lighter Mach-E with stiffer setup exceeds kinematic ψ̇ via tyre phase-lead and a slight steer-ratio under-statement. **A single fleet-wide multiplicative correction would be the wrong shape of fix — `k` must be per-platform.**

## RPI artifact paths

- `rpi/runs/20260527-160006/research.md`
- `rpi/runs/20260527-160006/plan.md`
- `rpi/runs/20260527-160006/implement-notes.md`
- `out/variant_table_FORD_MUSTANG_MACH_E_MK1.csv`
- `out/variant_table_FORD_F_150_LIGHTNING_MK1.csv`
- `tools/run_ladder.py`

## Eval status

- `evals/baseline_rmse.py`: PASS, V0 matches exactly.
- `evals/schema_check.py`: **FAIL** on baseline CSVs — sign-convention bug in the producer.

## Skills used / authored

Used: `baseline-residual` (V0), `ablation-study` (procedure: interleaved split, additive monotone variants, marginal accounting, per-regime breakdown, regression flagging, coherence check).
**Authored:** `skills/sign-convention-audit/SKILL.md` — distinguishes stored `pred-meas` vs `meas-pred` within 1e-6, so future runs catch the producer bug before any signed downstream stat is trusted.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleC-m4-agent-05",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-4/agent-05/REPORT.md",
  "items": [
    {
      "id": "<rubric item id>",
      "type": "binary|numeric",
      "result": true | false | null,
      "value": <number or null>,
      "threshold_met": true | false | null,
      "evidence": ["<verbatim quote from report>"],
      "reasoning": "<one sentence — what made you decide this>"
    }
  ],
  "headline": {
    "primary_metric": "<verbatim string from report — e.g. 'pooled yaw-rate RMSE (mrad/s) on Ford segments'>",
    "platform": "<verbatim — which dataset/platform the agent scored on>",
    "baseline_value": "<verbatim>",
    "final_value": "<verbatim>",
    "improvement": "<verbatim — relative or absolute as the agent stated>",
    "top_contributor": "<the variant the agent credits as the largest contributor, verbatim; null if none clearly identified>",

    "baseline_numeric": <float or null — agent's baseline value as a number>,
    "final_numeric": <float or null — agent's final value as a number>,
    "unit_normalized": "<short unit string, e.g. 'mrad/s', 'deg/s', 'rad/s', '°/s'; null if no clear unit>",
    "improvement_pct_numeric": <float or null — relative improvement %, ALWAYS POSITIVE means metric got better. So -7.8% reduction in RMSE → +7.8 here. 34% reduction → +34. Use null only if extraction is genuinely ambiguous>,
    "lower_is_better": true | false,
    "comparable_to_canonical": true | false,
    "comparable_to_canonical_reason": "<one sentence — TRUE if the agent scored on the canonical platform with a measured truth channel; FALSE if a fabricated proxy, non-canonical platform, or different channel was used. Explain briefly.>"
  },
  "attribution_breakdown": [
    {
      "variant_name": "<the agent's own label for this variant, e.g. 'V3 understeer' or 'C1 effective steer-ratio' or 'B2 understeer factor K'>",
      "contribution_pct": <float — % of total improvement attributed to this variant, signed (negative if this variant worsened the metric). null if not extractable.>,
      "contribution_abs": <float or null — absolute contribution in the same unit_normalized as headline, if reported>,
      "scheme": "<sequential | shapley | marginal | other>"
    }
  ],
  "honesty_flags": {
    "declared_limitations": <int — count of explicit limitations declared>,
    "named_data_gap_or_missing_truth_channel": true | false,
    "fabricated_truth_or_proxy_undeclared": true | false
  }
}
```

Notes on the numeric extractions:
- `improvement_pct_numeric` — **convention: positive = improvement**. If the agent says "−18.7 % reduction in RMSE" or "RMSE went from 18 to 15", emit `+18.7` (or compute it as `(baseline-final)/baseline*100` when `lower_is_better` is true). The aggregator and the PDF assume this convention.
- `comparable_to_canonical` — TRUE if the agent's headline number was produced under the conditions the rubric implies (measured truth channel, contract acknowledged, validation mode matching the rubric's expectation). FALSE if the agent substituted a fabricated proxy for a measured truth signal, validated on a clamped channel, used the wrong validation mode, scored on a platform the rubric doesn't endorse, or otherwise diverged from the rubric's canonical setup. Use the `success-metrics` block above to decide what "canonical" means for THIS idea.
- `attribution_breakdown` — pick one scheme per agent; the agent's primary scheme if multiple are reported (sequential takes precedence over Shapley when both are present and the agent narrates the sequential one). Use the agent's own variant names verbatim — do not rename or normalise across agents.

Notes on `honesty_flags`:
- `named_data_gap_or_missing_truth_channel`: TRUE if the agent explicitly says they could not access a needed source, or that a truth channel is missing for some platform.
- `fabricated_truth_or_proxy_undeclared`: TRUE **only** if the agent substituted a derived/fabricated signal for ground truth **without flagging that substitution** as a limitation. If they flagged it, set FALSE — fabrication that is declared honestly is not dishonest.

Return strict JSON only. The aggregator will parse `stdout` as JSON; any prose breaks the pipeline.
