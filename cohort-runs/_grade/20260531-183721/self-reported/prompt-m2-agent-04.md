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

- **agent_id**: m2-agent-04
- **report path**: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-04/final-model/REPORT.md`

## The report

```markdown
# Lateral-fidelity model — agent-04 report

## Approach

Per-platform steady-state bicycle model with a small first-order yaw-rate lag.

For each sample:

    delta_eff = delta_road_rad - delta_offset
    yr_ss     = v * delta_eff / (L_eff + K_us * v^2)
    yr[i+1]   = yr[i] + min(1, dt[i]/tau) * (yr_ss[i] - yr[i])

This replaces the V0 kinematic-single-track `yr = v * tan(delta) / L` with the linear bicycle steady-state expression, which natively captures understeer (`K_us * v^2` in the denominator). The first-order lag absorbs a small amount of un-modelled tire/actuator delay. Both Ford platforms benefit; the Tesla path falls back to V0 passthrough because there is no truth channel to fit against.

## Coefficient fit

- **Train/dev**: 70/30 random segment split per platform (seed=7) over all 415 segments in `data/sim/segments/FORD_*/**/sim.csv`.
- **Steering offset (`delta_offset`)**: median of `delta_road_rad` over samples where `|yaw_rate_meas_rads| < 0.003` and `|delta_road_rad| < 0.02` — captures rack/wheel-alignment bias.
- **`L_eff`, `K_us`**: Huber-IRLS linear regression of `v * (delta - d0) / yr_t ≈ L_eff + K_us * v^2` on cornering samples (`|yr_t| > 0.02`, `|delta - d0| > 0.005`, `v > 5 m/s`, ratio ∈ (0.5, 30) to drop sign-flipped outliers).
- **`tau`**: per-platform grid search on training segments, minimising yaw-rate RMSE.

Fitted values:

| platform                    | delta_offset (rad) | L_eff (m) | K_us       | tau (s) |
|-----------------------------|--------------------|-----------|------------|---------|
| FORD_F_150_LIGHTNING_MK1    | 0.000516           | 3.983     | 0.00292    | 0.05    |
| FORD_MUSTANG_MACH_E_MK1     | 0.000308           | 2.554     | 0.00185    | 0.08    |

Nominal wheelbases are 3.70 m (Lightning) and 2.984 m (Mach-E). Fitted `L_eff` differs from nominal because the steady-state bicycle bundles steering-ratio and tire-stiffness biases into a single effective term. The Lightning's much larger V0 residual (yaw RMSE 0.0163 vs Mach-E 0.0136) is mostly a *scale* problem (V0 over-predicts yaw by ~35%); the new fit corrects it.

## Results on held-out dev (30%, 125 segs)

| KPI                     | V0       | V_final  | Δ        |
|-------------------------|----------|----------|----------|
| Yaw-rate RMSE (rad/s)   | 0.01433  | 0.00711  | -50%     |
| Distance-CTE RMSE (m)   | 144.18   | 92.86    | -36%     |

Per-platform on dev:

| platform                  | V0 yaw   | Vf yaw   | V0 CTE  | Vf CTE  |
|---------------------------|----------|----------|---------|---------|
| FORD_F_150_LIGHTNING_MK1  | 0.01617  | 0.00635  | 132.89  | 57.21   |
| FORD_MUSTANG_MACH_E_MK1   | 0.01279  | 0.00763  | 151.12  | 110.13  |

## Results on full Ford eval (415 segs, ~1.05M samples)

| KPI                     | V0       | V_final  |
|-------------------------|----------|----------|
| Yaw-rate RMSE (rad/s)   | 0.01479  | 0.00839  |
| Distance-CTE RMSE (m)   | 151.998  | 113.719  |

Per-regime yaw-rate RMSE (full data, v > 2 m/s):

| regime    | V0       | V_final  |
|-----------|----------|----------|
| straight  | 0.00945  | 0.00670  |
| steady    | 0.02812  | 0.01252  |
| transient | 0.03825  | 0.02041  |

## What didn't help (and was tried)

- **Per-segment fitted delta offset** would buy ~0.001 rad/s on the Mach-E but cannot be applied at inference time (the grader has no segment-bias fitter). Would not generalise.
- **τ > 0.10 s** hurts steady-state RMSE more than it helps transients.
- **Trying to fit Tesla**: no `yaw_rate_meas_rads` truth channel in the sim CSVs — Tesla path is V0 passthrough.

## Skill usage

- `score-model/` — used heavily as the inner loop for the tau sweep and dev/full evaluation. Unmodified.
- `pre-flight-final-model/` — used to validate the final bundle; 9/9 checks pass.
- `load-segments`, `compare-models`, `make-train-dev-split`, `visualise-segment` — bypassed; a 10-line glob + `random.Random(7).shuffle` was shorter than loading the skill, and the residual story was clear enough that visualisation wasn't on the critical path.

## Caveats / next steps

- Fit is calibrated on Ford only; Tesla path returns V0 unchanged.
- Transient regime still carries ~0.020 rad/s residual. Next steps: a higher-fidelity ST single-track model with the openpilot-canonical cornering stiffnesses already in `code/parameters.py`, or a learned residual on `(v, delta, ddelta/dt, a_lat)`.

```

## Output — STRICT JSON ONLY

No prose around it, no markdown fence. **Write it to `/Users/javiquix/Desktop/quixdev/webinar-AI/_grade/20260531-183721/self-reported/m2-agent-04.json`** using your Write tool, then return the same JSON as your final response.

```json
{
  "agent_id": "m2-agent-04",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-04/final-model/REPORT.md",
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
