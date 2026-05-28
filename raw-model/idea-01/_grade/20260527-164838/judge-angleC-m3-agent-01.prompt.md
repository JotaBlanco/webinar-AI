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

- agent_id: **angleC-m3-agent-01**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-3/agent-01/REPORT.md`

```markdown
# Module-3 / agent-01 (angle-C) — Lateral fidelity

## Headline

Per-platform yaw-rate **scalar gain** is where the lateral fidelity gain hides. On the F-150 Lightning it cuts overall test-set RMSE 19.7% (0.02037 → 0.01636 rad/s). On the Mach-E it cuts 2.8% (0.01613 → 0.01568 rad/s). A per-platform static **bias** is near-null on Mach-E (+1.1 mrad/s) and small on F-150 (+4.6 mrad/s). Bias and gain pull the **opposite direction** between the two Fords — `g_MachE=1.095`, `g_F150=0.867` — so any single workshop-wide multiplier would regress one platform.

## Variants — incremental accounting

TEST split: interleaved every-5th sample (rule 7). Fit on TRAIN only. Per-platform (rule 8). Coupled `a_y_pred = v·ψ̇` recomputed (rule 9). Same segments + regime mask across all variants (rule 11).

| Variant | What | Mach-E ΔoverallRMSE | F-150 ΔoverallRMSE |
|---|---|---|---|
| V0 baseline | `ψ̇_pred` as-shipped | — (0.01613) | — (0.02037) |
| V1 +bias | `ψ̇' = ψ̇ − median(resid_straight)`, per-platform | -0.00002 (no-op) | -0.00030 |
| V2 +bias+gain | `ψ̇'' = g·ψ̇'`, fit on STEADY+TRANSIENT TRAIN | -0.00045 | -0.00371 |
| Total |  | **-0.00045 (2.8%)** | **-0.00401 (19.7%)** |

## Per-regime RMSE (rad/s, TEST set)

Mach-E V0/V2: straight 0.00878/0.00977 (**regression**), steady 0.03147/0.02979, transient 0.05743/0.05029.
F-150 V0/V2: straight 0.00899/0.00636, steady 0.03629/0.02869, transient 0.05161/0.04478.

## Per-segment vs per-platform label

All fits are **per-platform**. Per-segment bias removal explicitly skipped (rule 8 — calibration, not model improvement).

## Regressions flagged with physical cause

- **Mach-E straight regime regresses under V2** (0.00878 → 0.00977 rad/s). Cause: `g=1.095` amplifies near-zero pred-side noise/bias in straights, where the gain's physical motivation (steady-state understeer) doesn't apply. A regime-switched gain would fix it; out of locked scope.
- **Mach-E a_y_pred regresses 0.338 → 0.373 m/s² (coupled refit).** Cause: lateral-G truth carries a calibration offset that the ψ̇-only ladder cannot address. F-150 a_y RMSE ~10 m/s² flags a separate channel-scaling problem, not in scope.

## Painful absence

A model rerun with corrected steering ratio in `parameters.py`. The right place for the gain physically is `i_s` / `L`, but re-running KS over 545 segments was out of budget; the V2 multiplier is mathematically equivalent for `tan(δ)` small but doesn't update `a_y` consistently across all derivations.

## Near-misses

- A steering-lag fit (sub-sample cross-correlation) — would have attacked transient RMSE directly but was deliberately deferred.
- Per-platform `L_eff` instead of `g` — equivalent in the small-angle regime; chose `g` for closed-form linear fit.

## Surprise

The two Fords need **opposite-sign gain corrections**. Mach-E: KS under-predicts yaw rate (real car turns harder than KS — rear-biased mass distribution, rear stiffer than front). F-150: KS over-predicts (heavy truck, soft rubber, column compliance). One model, two platforms, two corrections — the per-platform discipline of rule 8 is the only honest accounting.

## RPI artifacts

- `rpi/runs/20260527-155925/research.md`
- `rpi/runs/20260527-155925/plan.md` (LOCKED, no deviations)
- `rpi/runs/20260527-155925/implement-notes.md`

## Eval status

- `evals/baseline_rmse.py` V0 numbers reproduced inside `tools/lateral_ladder.py` (test-set matches whole-set to 4 d.p.).
- `evals/schema_check.py` on `out/FORD_MUSTANG_MACH_E_MK1/sim_V2.csv` → PASS.
- `evals/schema_check.py` on `out/FORD_F_150_LIGHTNING_MK1/sim_V2.csv` → PASS.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleC-m3-agent-01",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-3/agent-01/REPORT.md",
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
