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

- **agent_id**: m1-agent-04
- **report path**: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-04/final-model/REPORT.md`

## The report

```markdown
# agent-04 — Lateral-Fidelity Submission

## Headline numbers (held-out validation, 80/20 split by route)

| Platform | Yaw RMSE V0 | Yaw RMSE V3 | Yaw improvement | XTE RMSE V0 (m) | XTE RMSE V3 (m) | XTE improvement |
|----------|------------:|------------:|----------------:|----------------:|----------------:|----------------:|
| FORD_F_150_LIGHTNING_MK1 | 0.01391 rad/s | **0.00490 rad/s** | -64.8% | 159.54 | **46.71** | -70.7% |
| FORD_MUSTANG_MACH_E_MK1 | 0.01688 rad/s | **0.01541 rad/s** | -8.7% | 108.82 | **81.05** | -25.5% |

XTE is distance-resampled at ds = 1 m, RMSE over all distance samples in all val segments. Tesla is not in the eval pool — see "Limitations".

## Model

Speed-known kinematic single-track (KS) with three calibrated corrections layered on top of the V0 baseline:

```
delta_eff[k] = lowpass_tau( delta_road[k] - delta_off )
psi_dot[k]   = a * (v[k] / L) * tan(delta_eff[k]) / (1 + b * v[k]^2)
trajectory   = forward-Euler integrate psi_dot with measured v
```

Per-platform coefficients (in `coeffs.json`):

| | L (m) | a | b | delta_off (rad) | tau (s) |
|---|---:|---:|---:|---:|---:|
| F-150 Lightning | 3.700 | 0.913 | 7.69e-4 | 1.22e-3 | 0.064 |
| Mach-E | 2.984 | 1.160 | 8.02e-4 | 1.37e-5 | 0.069 |

Interpretation:
- `a < 1` (Lightning) or `> 1` (Mach-E): residual steering-ratio / effective-radius bias not captured in V0.
- `b ~ 8e-4 s²/m²` on both: classic understeer gradient — yaw gain rolls off with v², exactly what the dynamic bicycle model predicts (linearised, K_us/L).
- `tau ~ 65 ms`: lumped lag between commanded delta and tyre-effective delta (rack compliance + tyre relaxation length).
- `delta_off`: Mach-E offset is ~zero; Lightning shows ~1.2 mrad — likely alignment / sensor zero bias.

## Ladder

- **V0** — provided `(v/L) tan(delta)`. Control.
- **V1** — `a * (v/L) tan(delta) / (1 + b v^2)`. Two-param understeer fit. Biggest single jump on Lightning (val 0.01391 -> 0.00659).
- **V2** — add constant `delta_off`. Helped Lightning slightly (0.00659 -> 0.00535); Mach-E offset fits to noise.
- **V3 (shipped)** — V2 + first-order lag `tau` on the steering. Helped both; Lightning val 0.00535 -> 0.00490, Mach-E val 0.01583 -> 0.01541.

All four parameters jointly fit per platform via Nelder-Mead on yaw-rate MSE over the train split. No leakage: val routes are entirely disjoint from train routes.

## Limitations

- **TESLA_MODEL_3 falls through to V0 identity.** Tesla `sim.csv` files have no `yaw_rate_meas_rads` column, so I cannot fit.
- Mach-E val improvement is modest. A per-speed-bin gain or a true ST (linear-bicycle, slip-aware) model would likely close more.
- Trajectory integration is forward-Euler (dt=20 ms). Switch to RK4 if grader is sensitive.

```

## Output — STRICT JSON ONLY

No prose around it, no markdown fence. **Write it to `/Users/javiquix/Desktop/quixdev/webinar-AI/_grade/20260531-174807/self-reported/m1-agent-04.json`** using your Write tool, then return the same JSON as your final response.

```json
{
  "agent_id": "m1-agent-04",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-04/final-model/REPORT.md",
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
