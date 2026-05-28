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

- agent_id: **angleC-m4-agent-04**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-4/agent-04/REPORT.md`

```markdown
# Module-4 / agent-04 (angle-C) — Lateral fidelity ladder

## Headline

Two-platform variant ladder over `yaw_rate_resid_rads` improves overall TEST RMSE by **+1.7%** on FORD_MUSTANG_MACH_E_MK1 (0.01613 → 0.01585 rad/s) and **+18.4%** on FORD_F_150_LIGHTNING_MK1 (0.02037 → 0.01662 rad/s). The dominant lever in both cases is **per-platform steering-gain calibration** (V3). All fits are per-platform on a 4:1 interleaved train/test split. Tesla excluded (no truth channel). Truth = `yaw_rate_meas_rads` (Ford CAN). `v` and `δ` are clamped to measured; KS predicts only lateral states.

## Variant ladder — Mustang Mach-E (TEST, rad/s, n_test=182 725)

| Variant | overall | straight | steady | transient | marginal | scope |
|---|---|---|---|---|---|---|
| V0 baseline (as-is) | 0.01613 | 0.00875 | 0.03162 | 0.05712 | — | per-platform |
| V1 bias removal (b=+0.00075) | 0.01613 | 0.00872 | 0.03170 | 0.05719 | -0.00001 REGRESSION | per-platform |
| V2 lag alignment (-1 sample, -20 ms) | 0.01635 | 0.00886 | 0.03170 | 0.05892 | +0.00021 REGRESSION | per-platform |
| V3 steering gain (k=1.0941) | 0.01590 | 0.00988 | 0.02995 | 0.05195 | -0.00045 | per-platform |
| V4 speed-residual (a=-0.0023, b=+1.1e-4/mps) | 0.01585 | 0.00985 | 0.02984 | 0.05184 | -0.00005 | per-platform |

Attribution coherence: 0.0000 (< 0.15 OK).

## Variant ladder — F-150 Lightning (TEST, rad/s, n_test=133 428)

| Variant | overall | straight | steady | transient | marginal | scope |
|---|---|---|---|---|---|---|
| V0 baseline (as-is) | 0.02037 | 0.00898 | 0.03619 | 0.05186 | — | per-platform |
| V1 bias removal (b=+0.00443) | 0.02006 | 0.00798 | 0.03624 | 0.05186 | -0.00031 | per-platform |
| V2 lag alignment (-1 sample, -20 ms) | 0.02031 | 0.00810 | 0.03631 | 0.05336 | +0.00025 REGRESSION | per-platform |
| V3 steering gain (k=0.8665) | 0.01662 | 0.00648 | 0.02860 | 0.04668 | -0.00368 | per-platform |
| V4 speed-residual (a=-3.9e-4, b=+2.3e-5/mps) | 0.01662 | 0.00649 | 0.02860 | 0.04667 | -0.00000 | per-platform |

Attribution coherence: 0.0000 (< 0.15 OK).

## Regressions (flagged, kept in ladder)

- **V2 lag alignment regresses on both platforms.** Best integer shift on TRAIN is -1 sample, but TEST RMSE worsens. Physical cause: KS is integrated forward over clamped `v, δ` already aligned with `yaw_rate_meas_rads`. There is no real lag — the TRAIN minimum is fitting residual autocorrelation, exactly the failure the interleaved split is designed to catch.
- **V1 bias removal regresses on Mustang** (≈1e-5). Mustang's residual median is ~0.75 mrad/s — sub-noise. F-150's is +4.4 mrad/s (a real sensor zero offset), which is why V1 helps there.

## Painful absence

None. Both `baseline-residual` and `ablation-study` skills covered the ladder. No new skill authored.

## Near-misses / surprise

- **Sign-convention bug in source data.** `yaw_rate_resid_rads` in every `sim.csv` equals `meas − pred`, not `pred − meas` per ratchet rule #1. RMSE is sign-insensitive so V0 is unaffected, but `evals/schema_check.py` FAILS on stock CSVs (max diff 1.4e-1). Anyone using residual *sign* downstream would be inverted. My ladder computes `pred − meas` directly, so attribution signs are correct. **Recommend fixing `code/generate_simdata_ford.py`.**
- **k goes opposite ways on the two Fords:** k=1.094 (Mustang under-predicts ~9%) vs k=0.867 (F-150 over-predicts ~13%). Almost certainly the steering-rack ratio / wheelbase in `PARAM_BY_PLATFORM` is off; truck has the larger error.

## RPI artifacts

- `rpi/runs/20260527-1555/plan.md`
- `rpi/runs/20260527-1555/implement-notes.md`
- `rpi/runs/20260527-1555/ladder_mustang.txt`
- `rpi/runs/20260527-1555/ladder_f150.txt`
- `tools/run_ladder.py`

## Eval status

- `evals/baseline_rmse.py` / `skills/baseline-residual/run.py`: V0 numbers match exactly (Mustang 0.01613, F-150 0.02037).
- `evals/schema_check.py`: **FAIL on stock CSVs** — sign convention bug in `generate_simdata_ford.py`, not introduced by this ladder.

## Skills used / authored

- Used: `skills/baseline-residual/` (V0), `skills/ablation-study/` (procedure). Custom runner `tools/run_ladder.py`.
- Authored: none.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleC-m4-agent-04",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-4/agent-04/REPORT.md",
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
