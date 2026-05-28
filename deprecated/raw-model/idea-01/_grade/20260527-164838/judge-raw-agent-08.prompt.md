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

- agent_id: **raw-agent-08**
- source path: `/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-08/REPORT.md`

```markdown
# Lateral-prediction improvement — KS bicycle model on Ford rlogs (agent-08)

## 1. Headline number

**Pooled yaw-rate RMSE across all 545 Ford segments (1.58M samples):**

- Baseline (raw KS, `psi_dot = v/L · tan(δ)`): **1.034 deg/s** (R² = 0.934)
- Final (offset + understeer + steer-ratio scale + lag align): **0.809 deg/s**
- **Reduction: 0.225 deg/s = 21.7 % of baseline RMSE**

Per-platform: F-150 Lightning 1.167 → 0.840 deg/s (-28.0%); Mach-E 0.924 → 0.786 deg/s (-15.0%).

I picked yaw-rate RMSE as the primary lateral-fidelity metric because (a) yaw rate is the canonical lateral-dynamics output that the KS equations directly predict, (b) `a_y = v · ψ̇` is just yaw rate scaled by measured speed so improving one improves the other, and (c) the Ford rlogs surface both `Yaw_Data_FD1.VehYaw_W_Actl` (yaw rate) and `BrakeSnData_3.VehLatComp_A_Actl` (a_y) as truth channels; yaw rate proved the cleaner signal.

## 2. What I implemented (ladder)

Each step is built per-platform on top of the previous, then results pooled.

- **V0 — Baseline**: stock KS as in `ks_model.py`: `psi_dot = v_meas/L · tan(δ_road)`. Read directly from the existing `sim.csv` columns.
- **V1 — Data cleanup**: drop samples with `|a_lat_meas| > 20 m/s²` (89 outliers in the F-150 truth channel — see surprises). No effect on yaw-rate RMSE (it was just nuking the a_y RMSE explosion); kept for honesty.
- **V2 — Steering zero-offset**: subtract a fitted constant δ₀ from `δ_road`. Captures rack-centre miscalibration. Fits to roughly 0.035° (F-150) and 0.007° (Mach-E) at the steering wheel — small but non-zero.
- **V3 — Linearised-bicycle understeer correction**: replace `v/L · tan(δ)` with the steady-state bicycle equation `ψ̇ = v/(L + K_us·v²) · δ_eff`. One scalar `K_us` fit per platform. Captures the kinematic-vs-dynamic gap (tyre slip at speed).
- **V4 — Steering-ratio scale**: joint refit of `(k_sr, δ₀, K_us)` allowing a multiplicative correction on `δ_road`. This is testing whether the documented `i_s` (steerRatio from carParams) is right.
- **V5 — Lag compensation**: integer-sample shift (at 50 Hz, dt = 20 ms) of prediction vs measurement. Both platforms preferred a +1 sample (20 ms) shift.

## 3. Attribution

Two schemes; both agree on the ranking.

### Sequential (RMSE drop V_{k-1} → V_k, pooled across both platforms)

| Step | RMSE after (deg/s) | Drop (deg/s) | Share of total model improvement |
|---|---|---|---|
| V0 baseline | 1.034 | — | — |
| V1 clean | 1.034 | 0.000 | (data, not model) |
| V2 offset | 1.026 | 0.007 | **3.1 %** |
| V3 understeer | 0.899 | 0.128 | **57.0 %** |
| V4 scale | 0.812 | 0.087 | **38.5 %** |
| V5 lag | 0.809 | 0.003 | **1.3 %** |

### Shapley (averaged marginal contribution over all 6 orderings of {offset, understeer, scale}; lag dropped because negligible)

| Lever | Shapley share of RMSE reduction |
|---|---|
| Understeer correction (K_us) | **54.8 %** |
| Steering-ratio scale (k_sr) | **40.8 %** |
| Steering zero-offset (δ₀) | **4.4 %** |

The orderings agree: the dominant defect in the baseline KS model is missing tyre slip (understeer at speed), with a substantial secondary contribution from a steering-channel scale error that is platform-specific.

## 4. Surprises

1. **Mach-E steering ratio appears wrong by ~18 %.** Best-fit `k_sr = 1.178` against the documented `i_s = 17.0` (carParams) implies an effective ratio of **~14.4** — i.e. the road-wheel angle the model sees is 17 % smaller than reality. On the Mach-E this single lever alone closes 41 % of the residual; on the F-150 `k_sr = 0.953` is much closer to unity. The parameter file describes Mach-E values as "openpilot-canonical, no `[unverified]` flag" — so either openpilot's number is the rack ratio at a single position and the effective wheel-to-road-wheel ratio varies, or this is a real bug in `parameters.py`.
2. **F-150 truth channel has bursts of decoding garbage.** 89 samples have `|a_lat_meas| > 50 m/s²` (max 1057 m/s²!) on the F-150 only, all from one segment. The a_y RMSE in the existing CSVs is 10.92 m/s² because of these — about 4 orders of magnitude worse than reality. The yaw-rate truth channel is clean.
3. **Fitted understeer gradient.** F-150 `K_us ≈ 0.0033 s²/m`, Mach-E `K_us ≈ 0.0026 s²/m`. Both small (these are well-balanced EVs); the truck is more understeering than the crossover, which matches the physical intuition (heavier, higher CG, longer wheelbase).
4. **Time lag is just one sample (20 ms) in both vehicles** — once you fit `k_sr` and `K_us`, latency is basically gone. So `(v_meas, δ_road)` and `yaw_rate_meas` are already well aligned in the adapter; not a meaningful lever.
5. **R² goes from 0.934 → 0.969** pooled, but the residual that remains is the highly transient steering-rate component (tyre relaxation, ψ̈ inertia) that a steady-state bicycle model cannot capture. To go further we would need a true dynamic single-track ST model (already pinned in `parameters.py` as `MachEST` / `F150LightningST` with `C_alpha_f/r`, `I_z`, etc.) — that's the next rung and the parameters are sitting there.

## 5. Limitations

- **Tesla excluded** — Tesla CSVs don't carry the yaw-rate or lateral-accel truth channels (the Tesla DBC doesn't expose IMU values; per `_README.md` this is a known gap). I had no way to evaluate Tesla lateral predictions, so all numbers above are Ford-only.
- **a_y RMSE not reported as headline** because the F-150 truth channel is corrupted; cleaning to `|a_lat|<20` brings Mach-E to a sensible 0.34 m/s² baseline but I didn't iterate on it.
- **Couldn't access the canonical answer or prior solutions** (per instructions: `webinar-angle-*/modulo-*/` and `webinar-00/` off-limits — did not attempt). No comparison to a "right answer" — fits could be over- or under-corrected vs whatever model the workshop converges on.
- **Per-platform fits** rather than universal physics-based numbers. The reported `K_us` and `k_sr` are calibration constants, not first-principles values; I'd want next to: (a) verify the Mach-E `i_s` against an OEM source to decide if `k_sr = 1.18` is a parameter bug or a real ratio non-linearity, (b) implement the ST model (parameters are already there) and see how much of the remaining residual comes from yaw-inertia / tyre relaxation that a steady-state bicycle can't reach, (c) split residual analysis by speed bin and by |ψ̇| bin to characterise where the model still fails.
- **No harness friction** — `Write` worked fine for tool scripts under `tools/`; no blocked writes encountered.

## Artefacts produced

- `tools/baseline.py` — baseline metrics computation
- `tools/improve.py` — full V0→V5 ladder with per-platform fits and sequential attribution
- `tools/shapley.py` — Shapley attribution over the 3 model levers
- `out/all_ford.parquet` — pooled Ford sim data (1.58M rows)

```
ISOLATION_REPORT:
read_outside_allowed: []
attempted_blocked: []
shared_dir_writes: []
notes: "Worked entirely off the existing sim.csv outputs (no rlog re-decoding). Stayed strictly inside agent-08/, code/ and data/. Did not read any sibling agent folder, webinar-angle-*/modulo-*/, or webinar-00/. All fits and metrics restricted to Ford segments since Tesla CSVs lack the truth columns."
```

```

## Output — STRICT JSON ONLY. No prose before or after. No markdown code fence.

```json
{
  "agent_id": "raw-agent-08",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-08/REPORT.md",
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
