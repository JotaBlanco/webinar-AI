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

- agent_id: **angleC-m4-agent-03**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-4/agent-03/REPORT.md`

```markdown
# Module-4 / agent-03 (angle-C) — Lateral fidelity ladder

## Headline

Per-platform variant ladder on both Fords (Tesla excluded — no truth). Speed-known lateral-only KS contract held. Interleaved 4/1 train/test split; all RMSE numbers are held-out test RMSE.

- **F-150 Lightning:** 0.02037 → **0.01499 rad/s overall (-26%)**.
- **Mach-E:** 0.01613 → 0.01635 rad/s overall (**net regression**).

## Variants (per-platform fits, additive monotone)

| V  | DoF added                       | Mach-E overall | Lightning overall |
|----|---------------------------------|---------------:|------------------:|
| V0 | none (baseline)                 |    0.01613     |     0.02037       |
| V1 | constant `δ_offset`             |    0.01615     |     0.02015       |
| V2 | + understeer `K_us` (lin. bike) |    0.01639     |     0.01503       |
| V3 | + integer sample lag            |    0.01635     |     0.01499       |

Fitted: Mach-E `δ_off=-2.8e-4 rad, K_us=2e-4, lag=+1`; Lightning `δ_off=-7.8e-4 rad, K_us=4.5e-3, lag=+1`.

Per-regime test RMSE (V3): Mach-E 0.00825 / 0.03259 / 0.05974; Lightning 0.00521 / 0.02559 / 0.04392.

Marginals — Mach-E: V1 -1.3e-5 (regression), V2 -2.4e-4 (regression), V3 +4.1e-5. Lightning: V1 +2.2e-4, V2 +5.1e-3, V3 +4.2e-5. Attribution-coherence ≈ 0.00 on both (well under 0.15).

## Painful absence

Mach-E. The platform with the **best-tuned openpilot priors** (carParams direct from rlog) is where the linear-bicycle ladder runs out of headroom at the KS rung. V2 improves straight regime (0.00878→0.00828) but worsens steady and transient — `C_α` priors already over-encode understeer for steady cornering, and the transient residual is dominated by tyre-relaxation / actuator phase, which is ST-rung physics, not a KS tweak. Honest call: ship the Lightning fix, leave Mach-E alone at the KS rung.

## Near-misses

V3 (lag) lands at exactly **+1 sample (20 ms) on both platforms** — same direction, same magnitude. Almost certainly a `yaw_rate_meas` vs `delta_meas` capture skew in the measurement pipeline. Small effect (+4e-5) but cross-platform-consistent, more interesting than its size.

## Surprise

`evals/schema_check.py` **FAILS** on stored sim CSVs. Stored `yaw_rate_resid_rads = meas − pred`, not the convention's `pred − meas`. RMSE is unaffected (sign-squared away) so V0 stands — but this is exactly the failure ratchet item #1 was added to prevent. Bug lives in `code/generate_simdata_ford.py`. Flag for the team.

## RPI artifact paths

- `rpi/runs/20260527-160000/research.md`
- `rpi/runs/20260527-160000/plan.md`
- `rpi/runs/20260527-160000/implement-notes.md`
- `out/ladder/{FORD_MUSTANG_MACH_E_MK1.json, FORD_F_150_LIGHTNING_MK1.json, summary.json}`
- `tools/ladder.py`

## Eval status

- `baseline_rmse.py`: PASS, matches V0 above.
- `schema_check.py`: FAIL on stored CSVs (sign bug in generator).

## Skills used / authored

- Used: `skills/baseline-residual`, `skills/ablation-study`.
- Authored: none — both regressions were platform-specific physics ceilings, not recurring procedural failures.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleC-m4-agent-03",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-4/agent-03/REPORT.md",
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
