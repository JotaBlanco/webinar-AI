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

- agent_id: **raw-agent-10**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-10/REPORT.md`

```markdown
# Lateral-Prediction Improvement Report — agent-10

### 1. Headline number

**Primary metric:** RMSE of predicted yaw rate vs measured Yaw_Data_FD1 truth across **all 545 Ford segments** (both Mach-E and F-150 Lightning), restricted to moving samples (v > 2 m/s, N = 1,364,925).

| | Yaw-rate RMSE (rad/s) | vs baseline |
|---|---|---|
| **Baseline (stock KS, all samples)** | **0.01782** | — |
| Baseline (stock KS, moving only) | 0.01481 | −17% |
| **Final (V4, moving only)** | **0.00985** | **−45% vs raw baseline; −33% vs hygiene-clean baseline** |

Secondary metric — lateral-acceleration RMSE (a_y = v·ψ̇, m/s²): **0.386 → 0.269** (-30%) on moving samples. (Unfiltered F-150 a_y RMSE is ~11 m/s² and is dominated by a non-zero `VehLatComp_A_Actl` reading at v=0 — sensor / ground-tilt bias, not model error.)

### 2. What I implemented (ladder)

KS lateral output is `ψ̇ = (v/L)·tan(δ)`, `a_y = v·ψ̇`. δ comes from `StePinComp_An_Est / steerRatio`. Truth = `VehYaw_W_Actl` from `Yaw_Data_FD1`. All fits are per-platform on the full corpus, closed-form least squares.

- **V0** Baseline = the `yaw_rate_pred_rads` already in sim.csv (stock KS, openpilot-canonical parameters).
- **V1** **Steering zero-offset** δ_off (rad, road-wheel) — Mach-E: −0.0001, F-150: −0.0006. Tiny.
- **V2** **Time-lag alignment** — brute-force best integer-sample shift (max 0.5 s) of prediction vs measurement. Best lag: Mach-E 0 samples, F-150 1 sample (20 ms). Essentially nothing.
- **V3** **Effective steer-ratio fit** — multiplicative scale s on δ; equiv. `i_s_eff = i_s/s`. Mach-E: 17.0 → **15.6** (s=1.09), F-150: 16.9 → **18.9** (s=0.88). Absorbs steering-column / rack compliance and tyre slip in steady state.
- **V4** **Understeer-gradient term** — replace `ψ̇ = v·δ/L` with `ψ̇ = v·δ_eff / (L + K_us·v²)` (steady-state bicycle / Ackermann + understeer). Fitted K_us: Mach-E 0.0010 s², F-150 0.0018 s². Captures the v²-dependent understeer growth KS ignores.

### 3. Attribution

**Two accounting schemes reported (both honest, neither uniquely "true"):**

**A) Cumulative ladder (sequential drop-in)** — primary attribution. Total moving-only yaw-RMSE reduction V0→V4 = 0.00458 rad/s:

| Step | Δ RMSE | % of total |
|---|---|---|
| V0→V1 (δ-offset)         | +0.00018 | **3.9%** |
| V1→V2 (time-lag)         | +0.00000 | **0.0%** |
| V2→V3 (effective i_s)    | +0.00210 | **45.8%** |
| V3→V4 (understeer K_us)  | +0.00230 | **50.3%** |

**B) Standalone (each technique applied alone vs V0)** — sanity check:

| Technique | Δ RMSE alone |
|---|---|
| δ-offset | 0.00018 |
| time-lag | 0.00000 |
| effective i_s | 0.00205 |
| K_us (with stock i_s) | 0.00238 |

The standalone columns nearly add up to the cumulative gain, which means the techniques are **largely orthogonal** — there's no double-counting between the steer-ratio fit and the understeer term, even though both involve "scaling δ." That's because K_us multiplies the denominator by v² while s multiplies the numerator; they decouple at the v-distribution level.

**Bonus "data hygiene" attribution (not a model change):** dropping v ≤ 2 m/s samples drops RMSE from 0.01782 → 0.01481 (an additional 0.00301 rad/s). Reported separately because it isn't a model fix — it removes idling segments where KS trivially predicts ~0 yaw but the IMU records sensor bias.

### 4. Surprises

- **The "time lag" channel is dead.** I expected ~40–80 ms of CAN-to-IMU delay. Fitted lag is 0 (Mach-E) or 20 ms (F-150). Either the rlog resampler already aligned them or the Yaw_Data_FD1 signal is genuinely low-latency.
- **The steer-ratio correction goes opposite ways on the two platforms.** Mach-E wants i_s reduced 17.0 → 15.6 (car is *more* responsive than the spec'd ratio implies). F-150 wants i_s raised 16.9 → 18.9 (truck is *less* responsive). I'd have expected both to drift in the same direction (compliance always reduces effective angle), so the Mach-E direction is a small puzzle — possibly a road-wheel-vs-pinion convention mismatch in the adapter, or net oversteer due to rear-bias and stiff rear tyres.
- **The F-150 `VehLatComp_A_Actl` channel has a large stationary bias** (~ −0.15 m/s² at v=0) — visible in any segment that contains an idle. This made the raw a_y RMSE look like ~11 m/s² before filtering. The yaw-rate channel does not have this issue.
- **Bias offset δ_off is essentially zero** on both platforms — the Ford steering-pinion calibration is trustworthy. This is the *opposite* of what you'd see on most aftermarket harnesses.

### 5. Limitations

- I only worked the **steady-state lateral output** (`ψ̇`, `a_y`). I did not touch transient dynamics — body slip β, tyre relaxation length, ST cornering stiffness fit. The code has a ST-model stub waiting (parameters.py exposes `C_alpha_f`/`C_alpha_r`), but in 15 minutes I couldn't responsibly fit a coupled bicycle ODE across 1.4 M samples.
- I fit a single global `(δ_off, lag, s, K_us)` per platform. A **per-segment** or **per-driver** fit, or one segmented by speed bin, would probably reduce residuals further (especially for K_us, which physically depends on tyre temperature and load).
- I made no attempt to **decouple δ_off from i_s drift** — both are absorbing a partly shared affine-in-δ error term; a joint optimisation rather than the sequential V1-then-V3 approach would re-allocate the attribution.
- The Tesla segments were left out: their CSVs lack a measured yaw-rate truth channel (per the README), so RMSE is undefined there. Improvements presumably transfer but I have no way to score them.
- I did not read any sibling agent's outputs, any `webinar-angle-*/modulo-*/` folder, or `webinar-00/`. No harness blocks fired.

---

```
ISOLATION_REPORT:
read_outside_allowed: []
attempted_blocked: []
shared_dir_writes: []
notes: "Worked entirely inside ./agent-10/, ./code/ (read-only), and ./data/ (read-only). All artefacts under tools/ and out/. TodoWrite reminder ignored; task was short enough to track in head."
```

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "raw-agent-10",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-10/REPORT.md",
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
