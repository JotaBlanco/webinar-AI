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

- agent_id: **raw-agent-09**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-09/REPORT.md`

```markdown
# Lateral-Prediction Improvements — Agent 09

## 1. Headline number

**Primary metric: pooled yaw-rate RMSE over all 520 Ford segments (Mach-E + F-150 Lightning), masked to `v > 2 m/s` (1.36M samples).**

- Baseline KS model: **0.01474 rad/s** (~0.84 °/s)
- Tuned KS model:   **0.00894 rad/s** (~0.51 °/s)
- **Improvement: −39.4% RMSE**

Secondary (derived) metric — lateral-acceleration `a_y = v·ψ̇`:
- Baseline 0.386 m/s² → Tuned 0.270 m/s² (**−30.1%**)

Per platform:
- F-150 Lightning: 0.01677 → 0.00840 rad/s (**−49.9%**)
- Mach-E: 0.01317 → 0.00928 rad/s (**−29.5%**)

## 2. What I implemented

I worked directly off the per-segment `sim.csv` files (which carry `v_mps`, `delta_road_rad`, measured `yaw_rate_meas_rads`, `a_lat_meas_mps2`, and the baseline KS prediction). This let me synthesise alternative predictions cheaply without re-running the rlog decoders.

Four corrections were stacked on top of the existing baseline `ψ̇ = (v/L)·tan(δ_road)`:

- **V1 — yaw-rate bias offset.** Subtract a per-platform scalar `b` (residual mean). Cheap fix for any IMU offset / wheel-alignment drift. b≈+3.98 mrad/s for F-150, ≈+0.56 mrad/s for Mach-E.
- **V2 — refit steering-ratio scalar `k`.** Equivalent to replacing `i_s` with `i_s/k`. F-150 fit implies effective `i_s ≈ 18.93` (vs nominal 16.9 — a +12% rack ratio). Mach-E fit implies `i_s ≈ 15.57` (vs nominal 17.0 — a −9% rack ratio).
- **V3 — time alignment.** Per-segment search for best integer-sample lag between δ and measured ψ̇ at 50 Hz; took the median (`−3` samples for F-150, `−4` for Mach-E, i.e. **yaw rate leads steering by ~60–80 ms** — this is the EPS-to-bus latency).
- **V4 — linear understeer correction.** `ψ̇ = (v/L)·tan(δ)/(1 + K·v²)`. K fits ~4.6e-4 (F-150) and ~3.7e-4 (Mach-E), both positive and in the expected order of magnitude for a passenger EV (Ackermann under-steer at speed). This is the single most important physics term.

## 3. Attribution

**Scheme: Shapley value over the four corrections, allocating the total MSE-drop across all 24 (n!) ordering permutations.** This avoids the trap of standalone effects being miscredited because V2 and V4 are partially redundant (a fixed scalar steering scale can mimic a fixed-speed understeer slope).

Shapley % of total MSE-drop:

| Variant | F-150 | Mach-E |
|---|---|---|
| V1 — bias | 7.0% | 0.4% |
| V2 — refit `i_s` | 34.8% | **51.8%** |
| V3 — time align | 3.1% | 13.6% |
| V4 — understeer `K·v²` | **55.1%** | 34.3% |

(Standalone MSE-drop tells a different and misleading story — e.g. V2 alone and V4 alone each look responsible for >45% on the F-150 because they both partially absorb the constant turn-radius error.)

Pooled across platforms: V2 + V4 together account for ~85% of the gain, V1 ~3%, V3 ~9%.

## 4. Surprises

- **F-150 steering ratio is materially wrong** in the parameter file (16.9 nominal, ~18.9 implied — a 12% error that produces a 50% RMSE reduction once corrected). Mach-E is wrong in the other direction (17.0 nominal vs ~15.6 implied — 9%). These are the kind of numbers comma.ai's `carParams` is supposed to nail; either the rlog `carParams` itself was off, or the EPS angle has a nonlinear scale at small magnitudes.
- **Negative best-lag** (steering leads yaw by ~60–80 ms in the file's sample index, but the fit wants the *opposite* shift). Mechanically: the resample collapsed both channels onto a 50 Hz grid but the Ford EPS `StePinComp_An_Est` and the IMU `VehYaw_W_Actl` have different bus arrival delays. The adapter does no time-of-flight compensation.
- The F-150's persistent ~+3.6 mrad/s positive yaw residual at baseline (≈0.2 °/s) is **larger than the noise floor** — small but real. Subtracting it is cheap and probably worth shipping even before refitting any physics.
- The KS model already includes `a_long` quantities in the CSV but they're unused under `clamp_v_to_measured=True` — there is no lateral-prediction lever there, so I ignored them.

## 5. Limitations

- Worked only on already-generated `sim.csv` files. I did not re-run `generate_simdata_ford.py` with corrected parameters; my "tuned" numbers are reconstructed analytically from `(v, δ_road)` and the closed-form `ψ̇`. Because the speed-known clamp turns KS into a closed-form lateral predictor, this is exact for ψ̇ and ay — but a true integrator-loop fit (re-running with corrected `i_s`, etc.) would also affect heading/position channels which I did not evaluate.
- No held-out test set: I fit and report on the same pooled data. With ~1.4M samples and 4 global scalar fits per platform, overfitting is negligible, but a per-segment K-fold would be cleaner.
- Did not look at the Tesla segments because their CSVs lack the yaw-rate truth channel (commented as such in the README), so attribution against ground truth is impossible there.
- A real ST (single-track) refit would change attribution: V2 and V4 are KS-level proxies for the same physics ST gets right by construction. With ST I'd expect the V4 share to shrink and a new "lateral cornering stiffness" term to take its place.
- I did not access any of the forbidden paths (sibling agent folders, webinar-angle modules, webinar-00 metadata). No prompts blocked anything — I did not attempt to read them.

Artefacts written:
- `tools/baseline.py`
- `tools/improve.py`
- `tools/shapley.py`
- `tools/final_eval.py`
- `out/baseline_per_seg.csv`
- `out/improvement_report.json`
- `out/shapley.json`

```
ISOLATION_REPORT:
read_outside_allowed: []
attempted_blocked: []
shared_dir_writes: []
notes: "Worked entirely off pre-generated sim.csv files via the data/ symlink; no rlog re-decoding; no sibling/angle/webinar-00 reads attempted."
```

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "raw-agent-09",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-09/REPORT.md",
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
