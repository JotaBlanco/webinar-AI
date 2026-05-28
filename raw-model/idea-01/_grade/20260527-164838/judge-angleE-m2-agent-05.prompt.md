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

- agent_id: **angleE-m2-agent-05**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-2/agent-05/REPORT.md`

```markdown
# REPORT — lateral-fidelity workflow (workshop scaffold S2)

## Platform and contract

- Platform scored: **FORD_MUSTANG_MACH_E_MK1** (315 segments, 913,626 rows).
- `yaw_rate_meas_rads` is measured truth (Ford rlog IMU).
- Speed `v` and steering `δ` are **clamped** to measured throughout (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). The speed-known operating contract held for every variant; no regression was "fixed" by unclamping.

## Variant ladder

| variant | overall | straight | steady | transient |
|---|---:|---:|---:|---:|
| V0 (baseline KS)         | 0.01613 | 0.00877 | 0.03173 | 0.05680 |
| V1 (KS recalib + bias)   | 0.01469 | 0.00493 | 0.03168 | 0.05730 |
| V2 (Linear ST, prior Cα) | 0.01653 | 0.00701 | 0.03450 | 0.06234 |
| V3 (Linear ST, fit Cα)   | 0.01663 | 0.00700 | 0.03482 | 0.06266 |

V3 fit: `C_αf = C_αr = 1.5e5 N/rad`, `pegged=False` — but did not move from seed (see below).

## Attribution (change in overall RMSE, rad/s; negative = improvement)

- **V0→V1: −0.00144.** Almost entirely the per-segment yaw-gyro bias subtraction on straight rows. Straight-regime RMSE collapses 0.00877 → 0.00493 (−44%). The canonical-`L` recalibration is a no-op here — `code/parameters.py::MachEST.L` already matches the V0 wheelbase. Steady and transient barely move (steady −0.00005, transient +0.00050).
- **V1→V2: +0.00184 (regression).** Both steady (0.0317 → 0.0345) and transient (0.0573 → 0.0623) get worse. The openpilot prior `C_α` understeer term `K_us·v²` reduces predicted ψ̇ at high speed in a direction the Mach-E does not require; the linear-ST structural form is simply a worse forward model than recalibrated KS on this platform under the clamped contract.
- **V2→V3: +0.00010 (essentially flat, tiny regression).** L-BFGS-B did not move from the seed `(C_αf, C_αr) = (1.5e5, 1.5e5)`. Not pegged at the upper bound — pegged at the initial point. Under the clamped-`v`, clamped-`δ` contract, the gradient of overall-RMSE w.r.t. `C_α` is effectively zero at the seed; the tyre-stiffness lever the optimiser needs is exactly what the operating contract removes. The structural form, not `C_α`, is what's hurting V2/V3.
- **Sum of marginals vs total V0→V3 drop:** +0.00050 vs +0.00050. Identical — there's no interaction term in this sequential ladder, so attribution is exact.

**Bottom line on "how much did each change contribute":** the only positive contribution is V1's straight-rows yaw-gyro bias subtraction (−0.00144 overall, −0.00384 on the straight regime). V2 and V3 are regressions on this platform. Do not deploy linear ST with the openpilot prior or the fit `C_α` here.

## Regressions and physical reasons

- **V2/V3 regress past V0 overall** (0.01653 / 0.01663 vs 0.01613). The understeer term shrinks predicted yaw rate at speed; on the Mach-E sample, the KS over-prediction we hoped to cancel is small relative to the under-prediction the prior `C_α` introduces. Net: worse.
- **Transient regime worsens V0→V1** (0.05680 → 0.05730). A *straight-rows* bias estimate applied uniformly to transient rows is a model-mismatch tax. Small, expected, acceptable trade for the straight-regime win.
- **V3 fit did not move from seed.** Flagged: `pegged=False`, but functionally pegged at the L-BFGS-B initial guess. Workflow stops at V3 as the ladder prescribes; we do not relax clamps or re-weight the loss.

## Notes

- **Tool fix required to complete the workflow.** `tools/step4_run_st_upgrade.py` was written for dict-style parameter access (`P["L"]`), but `code/parameters.py::PARAM_BY_PLATFORM[...]` returns a `MachEST` dataclass instance. Patched in-place with a one-line dict-comprehension shim at line 48 (`P = {k: getattr(_P_obj, k) for k in (...)}`). No numerics changed by the fix; without it step 4 raises `TypeError: 'MachEST' object is not subscriptable` and the workflow cannot proceed. Recorded per AGENTS.md.
- **Painful absence.** The workflow stops at V3 by design. The honest finding is that no prescribed *structural* upgrade (V2 prior `C_α`, V3 fit `C_α`) improves on V1; the only improvement is V1's bias-removal trick, not a model upgrade. A V4 residual-learner rung is the natural next step and is deliberately forbidden at the workflow tier — that absence is the comparison point.
- **Surprise.** V1's win is concentrated entirely in the straight regime; steady and transient barely budge. The bias subtraction is doing yaw-gyro zeroing, not model improvement. Under a regime-weighted scoring rule (transient counts more) V1 would also look like a wash. Plus: V3's fit stuck at its seed because the clamped contract zeroes the gradient — the optimiser's silence is informative, not a bug.

## Limitations / isolation

- Read only this module's files plus `code/` and `data/` via symlinks. No reads or writes outside the module; no siblings, other angles, `_shared`, `_launch`, F1, or `raw-model` touched.
- Single platform (Mach-E); no cross-platform generalisation claimed.
- Step 5 wrote a skeleton REPORT.md; final prose delivered in the agent response per the friction rule (`Write` blocked on `report.*\.md$`).

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleE-m2-agent-05",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-2/agent-05/REPORT.md",
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
