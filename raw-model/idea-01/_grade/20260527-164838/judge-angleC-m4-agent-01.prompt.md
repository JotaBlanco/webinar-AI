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

- agent_id: **angleC-m4-agent-01**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-4/agent-01/REPORT.md`

```markdown
# Module-4 / agent-01 (angle-C) — Lateral fidelity ladder

**Headline:** A per-platform bias + scalar gain on `yaw_rate_pred_rads` drops held-out RMSE 2.4% on Mustang Mach-E and **19.0% on F-150 Lightning**. Gain is the load-bearing variant on both cars; bias matters only on F-150; a uniform 1-sample lag shift is a regression on both.

## Variants (test RMSE rad/s, interleaved every-5th split, per-platform fits)

**Mustang Mach-E** (V0=0.01613 → V3=0.01575, coherence 0.000)

| # | variant | overall | Δ | straight | steady | transient |
|---|---|---|---|---|---|---|
| V0 | baseline | 0.01613 | — | 0.00878 | 0.03147 | 0.05743 |
| V1 | +bias=0.00075 | 0.01614 | +0.00001 **REGRESSION** | 0.00874 | 0.03155 | 0.05750 |
| V2 | +gain=1.069 | 0.01558 | -0.00056 | 0.00947 | 0.02966 | 0.05148 |
| V3 | +lag1 (per-seg) | 0.01575 | +0.00017 **REGRESSION** | 0.00954 | 0.02970 | 0.05298 |

**F-150 Lightning** (V0=0.02037 → V3=0.01651, coherence 0.000)

| # | variant | overall | Δ | straight | steady | transient |
|---|---|---|---|---|---|---|
| V0 | baseline | 0.02037 | — | 0.00899 | 0.03629 | 0.05161 |
| V1 | +bias=0.00442 | 0.02006 | -0.00031 | 0.00799 | 0.03634 | 0.05161 |
| V2 | +gain=0.859 | 0.01635 | -0.00372 | 0.00629 | 0.02854 | 0.04519 |
| V3 | +lag1 | 0.01651 | +0.00016 **REGRESSION** | 0.00638 | 0.02855 | 0.04624 |

**Recommended ship: V2 per-platform.** Bias and gain belong in `PARAM_BY_PLATFORM`.

## Painful absence

None acutely felt — `baseline-residual` and `ablation-study` covered the run. Sub-sample lag would have been worth a skill, but only one variant exercised it.

## Near-miss

V3 lag wobbled near zero; an integer-sample shift over-corrected sub-sample lag → flagged regression rather than dropped.

## Surprise

`evals/schema_check.py` **FAILS** on every source `sim.csv` — stored `yaw_rate_resid_rads` equals `meas − pred` (matches to 8.9e-07), not `pred − meas` as the convention in AGENTS.md/CLAUDE.md states (max diff 9.79e-02). RMSE is sign-symmetric so V0 numbers are unaffected, but Ratchet item #1 (the encoded past failure) is **currently present in the data on disk**. My variants recompute residual fresh, so are correct under the documented convention.

## Cross-platform finding

Gains have opposite direction — Mustang KS *under*-predicts (1.069), F-150 KS *over*-predicts (0.859). A global gain is useless; per-platform is mandatory.

## a_y coupling

`a_y_pred = v·ψ̇_pred` propagates the gain correction one-to-one; did not refit `a_y` separately.

## RPI artifact paths

- `rpi/runs/20260527-155947/research.md`
- `rpi/runs/20260527-155947/plan.md` (LOCKED pre-implementation)
- `rpi/runs/20260527-155947/implement-notes.md`
- Tool: `tools/ablate_lateral.py`
- Outputs: `out/ablate_FORD_MUSTANG_MACH_E_MK1_20260527-160123.{csv,json}` and `…F_150_LIGHTNING_MK1_20260527-160129.{csv,json}`

## Eval status

- `baseline_rmse.py` Mustang+F-150 → V0 matches my V0 to 5 dp ✓
- `schema_check.py` → **FAIL** on every source sim.csv (pre-existing data convention bug)

## Skills used

- `baseline-residual` (metadata + cross-checked via `evals/baseline_rmse.py`)
- `ablation-study` (discipline implemented in `tools/ablate_lateral.py`)
- **No new skill authored** — no recurring procedural gap appeared.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleC-m4-agent-01",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-4/agent-01/REPORT.md",
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
