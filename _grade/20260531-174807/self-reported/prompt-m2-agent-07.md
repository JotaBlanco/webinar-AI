# Self-reported extraction — `grade-cohort-reports` iter 3 diagnostic

> Placeholders in `{{double-braces}}`. `prepare_self_reported.py` fills them per agent.

---

You are a **strict numeric extractor**. Your job is to read ONE agent's REPORT and pull out the numbers the agent themselves claimed for their model's performance. You are NOT scoring; you are NOT judging methodology; you are NOT verifying. You are reporting WHAT THE AGENT SAID.

Why this matters: another pipeline measures each agent canonically (re-runs their predict.py on a held-out pool). The gap between what they CLAIMED and what their model actually does is its own signal — calibrated reporters vs over-claimers.

## What to extract

For each agent, extract:

1. **Yaw-rate RMSE improvement %** — the agent's headline claim of `(baseline - final) / baseline`. Positive = improvement. If the agent reports a "−55%" reduction, that's `+55.0` (positive). If they report multiple platforms separately, pick the one they lead with or feature most prominently; if there's a pooled / averaged figure, prefer that. If the agent says "not measured" or no number is given, return `null`.

2. **Yaw-rate RMSE baseline + final values** — raw numbers in their stated units. If they report per-platform, use the same platform you used for the percent above.

3. **CTE / cross-track error improvement %** — same shape as yaw. Some agents call it "CTE", "XTE", "dCTE", "distance-CTE", "cross-track error", or report it as "trajectory drift". Look for any of these. If no CTE number, return `null`.

4. **CTE baseline + final values** — raw numbers in their stated units (meters).

5. **What pool did they score on?** — one short phrase describing their evaluation set as they describe it (e.g. "70/30 held-out split on Ford segments", "all 415 Ford segments", "single-segment spot check"). Verbatim or near-verbatim.

6. **Declared limitations count** — count of things the agent explicitly called out as limitations or caveats. Bullets, "Limitations" sections, "What didn't help", etc.

## The agent

- **agent_id**: m2-agent-07
- **report path**: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-07/final-model/REPORT.md`

## The report

```markdown
# Lateral-fidelity v1 — agent-07

## Headline numbers (all 415 FORD_* segments, scorer = skills/score-model)

| Metric                  | V0 (baseline) | v1 (this model) | Delta    |
|-------------------------|---------------|-----------------|----------|
| Yaw-rate RMSE  [rad/s]  | 0.014794      | 0.008262        | -44.2 %  |
| CTE RMSE       [m]      | 151.998       | 117.418         | -22.7 %  |

Per-platform:

| Platform                  | V0 yr   | v1 yr   | V0 CTE  | v1 CTE  |
|---------------------------|---------|---------|---------|---------|
| FORD_MUSTANG_MACH_E_MK1   | 0.01362 | 0.00899 | 148.00  | 122.34  |
| FORD_F_150_LIGHTNING_MK1  | 0.01633 | 0.00710 | 157.51  | 110.04  |

Per-regime yaw-rate RMSE (v1 vs V0):
- straight   0.00689 (V0 0.00945)
- steady     0.01208 (V0 0.02813)
- transient  0.01795 (V0 0.03825)

A 70 % train / 30 % dev split (deterministic sort by segment path) was used for fitting. Dev-set yaw-rate RMSE confirmed the gain is not in-sample overfit: Mach-E dev 0.01067 vs train 0.00814, Lightning dev 0.00626 vs train 0.00742 (dev actually beat train, indicating no overfit).

## Model

For each Ford platform, a steady-state single-track bicycle with understeer-gradient correction and an output-side 1st-order causal low-pass:

    yr_raw   = v * c_s * delta_road / (L + K_us * v^2)
    yr_pred  = lowpass(yr_raw, dt, tau)

| Platform                  | L [m] | c_s    | K_us [s²/m] | tau [s] |
|---------------------------|-------|--------|-------------|---------|
| FORD_MUSTANG_MACH_E_MK1   | 2.984 | 1.2159 | 0.003205    | 0.08    |
| FORD_F_150_LIGHTNING_MK1  | 3.700 | 0.9770 | 0.003819    | 0.06    |
| TESLA_MODEL_3             |  -    |  -     |    -        |  -      |

For Tesla there is no `yaw_rate_meas_rads` truth in this cohort, so we pass V0 through and make no claim of improvement.

### Why each term

- **`c_s` (steering-angle scale).** V0 already converts the steering-wheel angle through the documented `steerRatio` to get `delta_road_rad`, but the residual analysis showed a constant gain offset versus truth. For the Mach-E the documented 17.0 ratio overshoots by ~21 % (real effective ratio ≈ 14). For the Lightning the 16.9 ratio is essentially correct (c_s ≈ 0.98).
- **`K_us` (understeer gradient).** The KS / kinematic model assumes the front and rear axles roll without lateral slip. Real tires slip more at higher speed, so V0 overshoots `yr` at speed. Bin-by-`v` correction factors before fitting confirmed monotonic drop from ~1.0 (low v) to ~0.55 (high v) — the canonical understeer signature. K_us ≈ 0.003 s²/m for both Fords, consistent with mildly understeer-tuned passenger EVs.
- **`tau` (output low-pass).** Cross-correlation of V0 vs truth across multiple segments showed a consistent +60 to +100 ms group delay (truth lags V0 pred). A 60–80 ms first-order RC low-pass on the predicted yaw rate reproduces that delay near-perfectly without the phase artefacts a fixed-sample shift would have introduced.

### Why not more

- Adaptive per-segment bias correction would help CTE (which integrates any mean yaw-rate residual into pure heading drift) but requires observing truth at predict time — out of scope for the deliverable contract.
- A full transient bicycle (the ST rung — `I_z`, `C_α_{f,r}`, `m`, `l_{f,r}` + an ODE integrator) was deferred. The current causal low-pass captures most of the actuator-side dynamics for far less complexity; the residual transient-regime RMSE (0.018 rad/s) is the obvious candidate for future ST work.
- The TESLA platform has no truth channel here; spending capacity on it would be unverifiable.

## Skills used

- `score-model/` — unmodified. Computes pooled yaw-rate RMSE and CTE RMSE plus per-platform / per-regime breakdowns. All headline numbers above come from this.
- `load-segments/` — unmodified. Used to iterate per-platform segments during fitting.
- `pre-flight-final-model/` — unmodified. All nine checks pass on the shipped bundle (after the parent persists this REPORT.md).
- `make-train-dev-split/` — bypassed. Used a deterministic 70 / 30 sorted-path split inline; load-segments already returns sorted results.
- `compare-models/` — not loaded. The scorer's per-regime / per-platform breakdown was enough signal.
- `visualise-segment/` — not loaded. Time budget was spent on fitting instead.

## Validation

`skills/pre-flight-final-model/preflight.py` reports `passes=True` on this bundle once REPORT.md is in place. Pre-fit, the only failing check is `report_md_present`; all eight functional checks (import, signature, return shape, no-NaN, manifest parsing) pass.

## Caveats

- Tesla rows are V0 passthrough; no improvement claimed for that platform.
- Fits used a deterministic 70 % train slice (sorted by segment path). A k-fold check was not run inside the time budget, but the spread between train and dev RMSEs was modest (under 30 %, with Lightning actually doing better on dev than train).
- The output low-pass introduces a small steady-state phase shift but no DC gain change; CTE benefits because heading-integrated phase errors are smaller than the raw sample-domain ones.
- If the grader's eval set overlaps the 70 % train split used here, the "-44 %" headline is mildly optimistic — but with only three scalar knobs per platform, overfit risk is small.

```

## Output — STRICT JSON ONLY

No prose around it, no markdown fence. **Write it to `/Users/javiquix/Desktop/quixdev/webinar-AI/_grade/20260531-174807/self-reported/m2-agent-07.json`** using your Write tool, then return the same JSON as your final response.

```json
{
  "agent_id": "m2-agent-07",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-07/final-model/REPORT.md",
  "extraction_status": "ok | no_quantitative_claim | ambiguous",

  "claimed_yaw_pct": <float | null>,
  "claimed_yaw_baseline": <float | null>,
  "claimed_yaw_final": <float | null>,
  "claimed_yaw_platform_scope": "<verbatim or null>",

  "claimed_cte_pct": <float | null>,
  "claimed_cte_baseline": <float | null>,
  "claimed_cte_final": <float | null>,
  "claimed_cte_platform_scope": "<verbatim or null>",

  "evaluation_pool_description": "<short verbatim or null>",
  "declared_limitations_count": <int>,

  "extraction_notes": "<one short sentence — e.g. 'Agent reports per-platform; picked Lightning since report leads with it. CTE not reported.' or 'Headline says NOT MEASURED — Python sandbox blocked execution.'>"
}
```

## Conventions

- **Positive = improvement.** If the agent says "−45% in RMSE" or "RMSE dropped 45%" → `+45.0`.
- **`null` is correct** when the agent didn't quantify something. Never guess.
- **`extraction_status="no_quantitative_claim"`** when the agent shipped a model but didn't report measured numbers (e.g. sandbox blocked python3, only theoretical analysis).
- **`extraction_status="ambiguous"`** when the agent reported several numbers and there's no clear "headline" to pick.
- **Do not normalise units.** Report what they reported. Aggregator handles unit checks.

Return strict JSON only.
