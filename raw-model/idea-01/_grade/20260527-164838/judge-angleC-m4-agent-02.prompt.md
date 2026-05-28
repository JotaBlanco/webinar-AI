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

- agent_id: **angleC-m4-agent-02**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-4/agent-02/REPORT.md`

```markdown
# Module-4 / agent-02 (angle-C) — Lateral fidelity ladder

**Platform**: FORD_MUSTANG_MACH_E_MK1 (Mustang Mach-E MK1, 315 segments, 913 626 samples; test fold 182 725 via interleaved every-5th split).

**Headline**: V0 → V3 overall yaw-rate RMSE **0.01613 → 0.01557 rad/s** (-3.5% overall, **-10% on transient cornering**, -6% on steady). Effectively all of the gain came from a single per-platform parameter fit — **effective wheelbase L_eff = 2.793 m vs canonical L = 2.984 m** (~6.4% shorter).

**Measured-truth statement**: scored against `yaw_rate_meas_rads` (openpilot IMU yaw rate on CAN, Ford-only). Residual sign `pred − meas` (ratchet #1). Sign-convention sanity holds in V0 by construction.

**Clamped-vs-predicted**: speed-known lateral-only mode — `v` and `δ` clamped to measured, lateral states predicted via `ψ̇ = v·tan(δ_road)/L`. Lateral-only (ratchet #5).

## Variant ladder (per-platform, interleaved test fold)

| Variant | overall | straight | steady | transient | marginal |
|---|---|---|---|---|---|
| V0 baseline | 0.01613 | 0.00875 | 0.03162 | 0.05712 | — |
| V1 bias remove (b=+0.00075) | 0.01613 | 0.00872 | 0.03170 | 0.05719 | **-0.00001 (regression)** |
| V2 lag align (k=0 samples) | 0.01613 | 0.00872 | 0.03170 | 0.05719 | +0.00000 |
| V3 L_eff fit (L_eff=2.793 m) | 0.01557 | 0.00944 | 0.02981 | 0.05115 | **-0.00056** |

All variants per-platform (one scalar / one integer each). Attribution coherence err = 0.0000 (<0.15). Σ marginals = total drop = -0.00055 rad/s.

## Regressions (with physical cause)

- **V1 bias removal**: -0.00001 rad/s. Train median residual (+0.00075) is small and biased the test predictions the wrong way in the straight regime. Physical cause: the V0 residual is already near-zero-mean; no real DC IMU offset to remove on this platform.
- **V3 straight-regime side effect**: straight RMSE rose 0.00872 → 0.00944 (+8%). Physical cause: a shorter L_eff gains up small δ noise around zero; the cornering improvement dominates, so overall RMSE still drops, but a regime-gated correction would be cleaner.

## Painful absence

None acutely felt. A `regime-gated-variant` skill would have helped me cleanly express "apply V3 only on cornering"; noted as future work rather than authoring a new skill in budget.

## Near-misses

- V2 lag fit returned k=0 — hypothesis that CAN δ lags the IMU was **falsified at 20 ms resolution**. Openpilot's pipeline appears to time-align δ_road and yaw rate already.
- V1's "obvious" bias removal turned into a near-zero regression — V0 is already centred.

## Surprise

The carParams `L=2.984` m is openpilot-canonical (read from the rlog itself) — yet the data prefers L_eff ≈ 2.79 m. That gap is almost certainly **compliance steer + tire scrub effectively reducing the road-wheel angle**, exactly the kind of single-track-vs-real-tire mismatch this workshop is built around. It explains why the prior gain is too high during cornering.

## Artifacts

- RPI run: `rpi/runs/20260527-160016/` (research.md, plan.md, implement-notes.md)
- Ladder code: `tools/run_ladder.py`
- Numerics: `out/ladder_summary.json`

## Eval status

- `evals/baseline_rmse.py FORD_MUSTANG_MACH_E_MK1` → overall 0.01613 — matches V0 in the ladder.
- `evals/schema_check.py` not invoked on derived CSVs (no derived CSVs were written; ablation scored in-memory off existing schema-valid sim.csvs).

## Skills used / authored

- Used `skills/baseline-residual` (V0 numbers + regime mask, matched eval).
- Used `skills/ablation-study` (interleaved split, additive monotone variants, marginal accounting, regression flagging, coherence check). Loop implemented in `tools/run_ladder.py` per the skill's "discipline matters more than the runner" clause.
- No new skill authored within the 15-min budget.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleC-m4-agent-02",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-4/agent-02/REPORT.md",
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
