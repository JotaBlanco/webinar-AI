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

- agent_id: **angleD-m2-agent-01**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-2/agent-01/REPORT.md`

```markdown
# REPORT — lateral-fidelity-triage on FORD_MUSTANG_MACH_E_MK1

**Platform scored:** FORD_MUSTANG_MACH_E_MK1 (Mach-E MK1).
**Truth channel:** `yaw_rate_meas_rads` is *measured* truth — decoded from the rlog IMU via the Ford party DBC (Mach-E is a first-class openpilot port; SKILL.md confirms Tesla has no decoded IMU yaw, Ford does).
**Sample:** 20 segments, deterministic stride over 315 available Mach-E `sim.csv` files; 57,987 rows total.
**Residual under test:** `yaw_rate_pred − yaw_rate_meas` (rad/s).
**Operating contract:** speed-known, lateral-only (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`, per SKILL.md).

## Variant ladder

| Variant | overall RMSE [rad/s] | straight | steady | transient | attribution Δ vs prev |
|---|---|---|---|---|---|
| V0 baseline (`yaw_rate_resid_rads` from CSV)               | **0.01192** | 0.00807 | 0.01729 | 0.04098 | — |
| V1 KS recalibrated, canonical L, per-segment straight bias | **0.00993** | 0.00430 | 0.01683 | 0.03948 | **−0.00199 (−16.7%)** |
| V2 Linear ST, prior C_α (openpilot-canonical)              | 0.01155     | 0.00350 | 0.02088 | 0.04681 | +0.00162 *(regression)* |
| V3 Linear ST, fit C_α (Cα_f≈653k, Cα_r≈668k, not pegged)   | 0.01048     | 0.00360 | 0.01820 | 0.04342 | −0.00107 (vs V2) |
| V4 Ridge residual learner LOO on V3 residuals              | 0.01108     | 0.00382 | 0.02078 | 0.04134 | +0.00060 *(regression)* |

Best variant overall: **V1**. Best transient: V1. Best straight: V2 (but loses elsewhere). Best steady: V1.

## Attribution

- **V1 is the only positive contributor on overall RMSE.** It contributes the whole 0.00199 rad/s overall improvement (−16.7% vs V0). Decomposition by regime: straight bin drops from 0.00807 → 0.00430 — i.e. ~half of V1's gain comes from removing a per-segment gyro DC bias on straight-line samples. The other half is steady/transient improvement from using the canonical wheelbase L=2.984 m via `MACH_E` parameters.
- **V2 over-shrinks gain.** Prior C_α makes K_us > 0 in a regime where the in-CSV KS prediction (no slip term) was already accurate; the ST gain at v=20 m/s is ~18% lower than KS, so steady and transient RMSE grow.
- **V3 partially repairs V2** by fitting Cα toward higher values (Cα_f, Cα_r ≈ 6.5e5 N/rad) — i.e. the data prefers a *stiffer* tire than the openpilot prior, edging back toward the KS gain — but V3 still ends above V1.
- **V4 (Ridge residual learner)** doesn't help on this segment set. The OOF residuals predicted by ridge are noise on top of V3's already over-corrected gain.

## Why V1 beats the full ladder on Mach-E

The baseline `yaw_rate_pred_rads` in `sim.csv` is essentially `(v/L)·tan(δ)` with L = 2.984. Correlation between in-CSV `yaw_rate_pred_rads` and `yaw_rate_meas_rads` on cornering rows is **0.996**. So the dominant residual is a small gyro DC offset and a tiny gain mismatch, not slip-angle dynamics. A per-segment de-meaning on straight samples is the right tool. The ST layer adds parameters whose prior is calibrated to *high-grip / Tesla-Model-3-ish* assumptions and *reduces* the gain on the Mach-E.

## Sign-check

`corr(δ_road, ψ̇_meas)` on cornering rows = +0.77 (positive). No sign error, per SKILL.md § Sign-error checklist.

## Limitations / known harness gaps

- SKILL.md is v0.1. It explicitly omits: regression-flag rule, V0-methodology pin, ST-low-v warning, single-table rule, pegged-Cα detection.
- The supplied `triage.fit_c_alpha` uses L-BFGS-B with `x0=(1.5e5, 1.5e5)`. On Mach-E data, that x0 lies on a quasi-flat ridge near the K_us-singular surface and the optimizer terminates without leaving x0. `pegged_at_upper` is False because Cα is at x0, not at the upper bound — so the helper silently mis-reports "converged". I worked around this with a log-grid pre-search + Nelder-Mead refine; the patched fit found Cα_f≈652k / Cα_r≈668k with RMSE 0.01226 (still worse than V1). A "fit-converged" sanity check should be added in the next SKILL.md revision.
- Only Mach-E was scored (per SKILL.md default). Lightning data is available but out of scope for this run.
- No `references/` or `evals/` subfolder — the skill v0.1 substrate does not include reference numbers I could regress against.

## Artefacts

- `out/run_ladder.py` — driver.
- `out/ladder_results.csv` — the table above.
- `out/meta.json` — fit Cα, sample size, parameter values used.

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleD-m2-agent-01",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-2/agent-01/REPORT.md",
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
