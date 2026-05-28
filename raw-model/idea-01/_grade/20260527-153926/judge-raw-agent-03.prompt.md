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

- agent_id: **raw-agent-03**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-03/REPORT.md`

```markdown
# Lateral-prediction improvement — agent 03 report

## 1. Headline
**Primary metric:** RMSE of yaw-rate prediction (rad/s), evaluated on a held-out 20 % segment-level test split, pooled across both Ford platforms (Mustang Mach-E MK1 and F-150 Lightning MK1) where the dataset includes a measured-yaw-rate truth channel.

| | Mach-E | F-150 Lightning | Mean |
|---|---|---|---|
| **Baseline RMSE (V0)** | 0.01087 rad/s | 0.01453 rad/s | **0.01270 rad/s** |
| **Final RMSE (V3)**    | 0.00847 rad/s | 0.00831 rad/s | **0.00839 rad/s** |
| **Relative reduction** | 22.1 %         | 42.8 %         | **33.9 %**     |

Across both platforms, the lateral (yaw-rate) RMSE was cut by roughly one third without touching `ks_model.py` — purely via fitted parameters and a swap from KS-kinematic to linear-bicycle-steady-state yaw.

## 2. What I implemented
The ladder is additive; each variant inherits the previous one's corrections.

- **V0 — baseline.** The KS prediction as recorded in the simdata CSVs: `ψ̇ = (v/L)·tan(δ_road)` with nominal `i_s` and zero offset.
- **V1 — steering-bias removal.** Subtract a per-platform scalar steering-wheel offset, estimated as the median `δ_road` on near-straight samples (|measured ψ̇| < 0.02 rad/s, v > 8 m/s). Fitted +0.30° (Mach-E) and −0.10° (F-150) at the steering wheel.
- **V2 — effective steer-ratio fit.** Replace the published nominal `i_s` with a single scalar `i_s_eff` per platform, fitted by least-squares on `ψ̇_meas = (v/L)·(δ − bias)/s`. Mach-E: 17.0 → **15.58**; F-150: 16.9 → **18.99**.
- **V3 — understeer-gradient correction (linear bicycle, steady-state).** Replace pure kinematic yaw with `ψ̇ = v·δ_eff / (L + K_us·v²)`. Fit `K_us` per platform by 1-D LS on `δ_eff − L·ψ̇/v = K_us · v·ψ̇`. Mach-E: K_us = 1.13 × 10⁻³ s²/m; F-150: 1.80 × 10⁻³ s²/m.

All three parameters were fit on the **train** split (≈80 % of segments, hashed deterministically) and the RMSE numbers above are reported on the disjoint **test** split. Only Ford segments were used because the Tesla simdata has no measured-yaw-rate truth channel (Tesla rlogs lack a decoded IMU on the open DBC).

## 3. Attribution

**Scheme A — marginal / sequential ablation** (drop in test-set RMSE when this variant is added on top of the previous one, divided by total V0→V3 drop):

| | Mach-E | F-150 Lightning |
|---|---|---|
| bias        | −5.0 % | −2.8 % |
| ratio       | +30.3 % | +69.2 % |
| understeer (K_us) | +74.7 % | +33.6 % |

**Scheme B — Shapley-style** (averaged marginal contribution across all 3! = 6 orderings of the three corrections):

| | Mach-E | F-150 Lightning |
|---|---|---|
| bias        | −3.0 %  | −3.6 % |
| ratio       | +58.3 % | +38.8 % |
| understeer  | +44.8 % | +64.8 % |

Bias is a near-zero / slightly negative contributor on both platforms — the offset is real but small enough that fitting it on the "near-straight" subset doesn't generalise. The two large-mass effects are the effective steer ratio and the understeer gradient, and Shapley redistributes some of V2's gain back to K_us because the ratio fit was partly compensating for missing understeer.

## 4. Surprises
- The fitted **effective steer ratio for the F-150 Lightning is 18.99 vs the published 16.9** — ~12 % higher. The Mach-E moves the other direction (15.58 vs 17.0). This is much larger than I expected for openpilot-canonical values that were claimed to be production-tuned.
- **Steering-bias correction by itself made things slightly worse** on both platforms. The near-straight cohort used to fit the bias is too small a slice to characterise the true offset, and the rest of the distribution doesn't share the same median. A combined fit (bias + ratio jointly) would likely recover the missing 5 % or so.
- The understeer coefficient `K_us` for the F-150 (1.8 × 10⁻³ s²/m) is notably larger than the Mach-E's (1.1 × 10⁻³), consistent with the Lightning's much heavier curb weight (3084 kg vs 2336 kg) and higher CoG — a sanity check the fits passed.
- The simdata CSV is rich enough that this exercise needed zero re-running of `simulate_ks` — every column required was already in `sim.csv` from `generate_simdata_ford.py`.

## 5. Limitations
- **Tesla excluded.** Tesla simdata has no measured yaw-rate truth channel, so I cannot quantify improvement there. The same parameter fits could be ported but would need an independent truth source (IMU reverse-engineering on the Tesla party DBC).
- **Linear-bicycle, not ST proper.** I used the steady-state form `ψ̇ = v·δ / (L + K_us·v²)`, not the transient single-track ODE with separate `C_α,f`, `C_α,r`. The full ST integration would likely shave another few percent in transients but would require touching `ks_model.py`. I deliberately stayed in post-processing scope to keep the ablation clean.
- **No tyre saturation / a_y-magnitude split.** All samples weighted equally; at high `|a_y|` (> 4 m/s²) the linear assumption breaks. A separate analysis would benefit from stratifying by `|a_y|`.
- **No cross-validation across segments / drivers.** The 80/20 split is a single shuffle. K-fold would give an uncertainty band on each attribution share.
- **Time budget.** Did not have time to write a closed-form joint LS fit for (bias, ratio_scale, K_us) — fitting them sequentially is suboptimal and explains why Shapley shares differ from sequential.
- **Honour-bound restrictions:** I did not read any sibling-agent folder, any `webinar-angle-*/modulo-*/`, or `webinar-00/`. The hook did not visibly block me.

Outputs saved:
- `tools/improve_lateral.py`
- `out/run2.txt`

```
ISOLATION_REPORT:
read_outside_allowed: []
attempted_blocked: []
shared_dir_writes: []
notes: "Ford simdata only — Tesla has no yaw-rate truth channel in this dataset, so reported gains cover Mach-E and F-150 Lightning. No reads outside agent-03/, ./code/, ./data/."
```

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "raw-agent-03",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-03/REPORT.md",
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
