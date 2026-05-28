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

- agent_id: **angleD-m2-agent-04**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-2/agent-04/REPORT.md`

```markdown
# REPORT.md — webinar-angle-D / module-2 / agent-04

## Setup
- Platform scored on: **Ford Mustang Mach-E (MK1)**.
- `yaw_rate_meas_rads` is **measured truth** decoded from the Mach-E IMU via the Ford party DBC in the rlog.
- Segment set: first 12 Mach-E `sim.csv` paths under `data/sim/segments/FORD_MUSTANG_MACH_E_MK1/` (34,786 rows, multiple devices/routes).
- Operating contract: `clamp_v_to_measured=True`, `clamp_delta_to_measured=True` (speed-known, lateral-only).
- Sign check: `corr(delta_road_rad, yaw_rate_meas_rads)` on cornering rows = **+0.939** → sign convention is correct.

## Variant ladder — RMSE of yaw-rate residual (rad/s)

| variant | overall | straight | steady | transient | Δ vs prev (overall) |
|---|---:|---:|---:|---:|---:|
| V0 baseline (CSV `yaw_rate_resid_rads`) | 0.01403 | 0.01261 | 0.03192 | 0.03796 | — |
| V1 KS recalibrated + per-segment yaw-gyro bias | 0.00973 | 0.00737 | 0.02924 | 0.04055 | **−0.00429** |
| V2 Linear ST with openpilot prior C_α | 0.00825 | 0.00351 | 0.03459 | 0.04544 | **−0.00148** |
| V3 Linear ST with fit C_α | 0.00839 | 0.00367 | 0.03517 | 0.04570 | +0.00014 (regress) |
| V4 Ridge residual learner (LOO) on V3 | 0.00999 | 0.00379 | 0.04116 | 0.05839 | +0.00160 (regress) |

(`Δ vs prev` is the contribution attribution requested by the skill — negative = improvement.)

## Attribution of the V0→V2 gain (Δ overall RMSE = −0.00578 rad/s, −41%)
- **74% (−0.00429)** from V1: re-deriving `ψ̇_KS = (v/L)·tan(δ_road)` with the canonical Mach-E `L = 2.984 m` **and** subtracting a per-segment straight-line yaw-gyro bias. The bias step alone explains most of this — straight-row residual went from 0.01261 → 0.00737.
- **26% (−0.00148)** from V2: switching to the linear-ST steady-state gain with the openpilot prior (`C_αf=286,551`, `C_αr=355,912`). Almost all of this lands in the **straight** regime (0.00737 → 0.00351); cornering RMSE actually worsens slightly.

## What did NOT work (and why)
- **V3 fit C_α regressed.** `triage.fit_c_alpha` returns `(150000, 150000)` — i.e. the initial guess `x0 = [1.5e5, 1.5e5]`. A grid scan over (5e4 … 5e5)² shows the loss surface has near-singular ridges where `1 + K_us·v² ≈ 0` (denominator in the gain formula explodes), and L-BFGS-B's numeric gradient at `x0` is dominated by those neighbouring NaN/Inf cells, so the optimiser declares convergence immediately. True grid minimum is at ~(4e5, 5e5) with overall loss **0.01265**, only marginally below the prior's **0.01273** — i.e. the prior is already near-optimal on this segment set, and there is no real headroom from fitting C_α. **Skill helper has a silent failure; should switch to a regularised / log-space param search, or grid-search seeded.**
- **V4 residual learner regressed** in steady and especially transient (0.0454 → 0.0584 rad/s). The feature set `[v, |a_y|, |δ|, sign(δ̇)]` includes only one transient signal (`sign(δ̇)`, a discrete ±1) and the OOF Ridge model overfits to per-segment offsets it cannot generalise. Recommendation: replace `sign(δ̇)` with continuous `δ̇`, add a tyre-load proxy (`v·δ̇`), and switch from Ridge to a non-linear model or at minimum bake the regime into the feature.

## Absent harness component I felt the lack of most
**An `evals/` fixture / regression-test directory** for the skill. `fit_c_alpha` silently returned its initial guess; I only caught it because I ran a one-off grid sanity check. A frozen `expected.json` with V0..V4 RMSE on a tiny known segment, or even a unit test that asserts `loss(fit) < loss(prior)`, would have flagged the broken optimiser immediately and removed the temptation to trust V3 at face value. The skill is also missing a `references/` page on which regimes the linear-ST formulation should and shouldn't be trusted in — that's why I can't tell whether the V2 cornering-regime degradation is expected (e.g. tyre saturation, suspension roll) or a sign of further bias.

## Recommended next steps
1. Patch `triage.fit_c_alpha` — seed from openpilot prior, search in log-space, mask out rows where `|1 + K_us·v²| < ε`.
2. Add an `evals/` fixture with a 2-segment regression test (`V2 ≤ V0`, `V3 ≤ V2`).
3. Re-spec V4: continuous `δ̇`, regime as a one-hot, per-segment effects removed before fit.
4. Investigate why V2 helps straight but hurts cornering — likely an unmodelled `a_y`-dependent compliance / tyre slip term beyond linear ST.

## Artefacts
- `out/run_ladder.py` — the ladder script
- `out/check_fit.py` — C_α grid sanity check
- `out/ladder_results.csv`, `out/fit_params.json`

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "angleD-m2-agent-04",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-2/agent-04/REPORT.md",
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
