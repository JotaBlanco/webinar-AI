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

- **agent_id**: m1-agent-02
- **report path**: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-02/final-model/REPORT.md`

## The report

```markdown
# agent-02 — lateral-fidelity submission

## Headline numbers (held-out 40% of segments per platform)

| Platform | Yaw RMSE V0 | Yaw RMSE Final | dCTE V0 | dCTE Final |
|---|---|---|---|---|
| FORD_F_150_LIGHTNING_MK1 (n=70) | 0.01225 rad/s | 0.00547 rad/s (-55%) | 71.8 m | 34.5 m (-52%) |
| FORD_MUSTANG_MACH_E_MK1 (n=96)  | 0.01196 rad/s | 0.00813 rad/s (-32%) | 72.9 m | 62.0 m (-15%) |

dCTE = distance-resampled cross-track-error RMSE, integrated over the full
~58-s segment with (yr_meas, v_meas) as the truth trajectory and
(yr_pred, v_meas) as the predicted trajectory, 1 m arc-length grid,
path-normal offset.

Tesla is not evaluated (no yaw_rate_meas_rads truth in its sim.csv);
the Tesla coefficients in coeffs.json are a sensible prior.

## Fidelity ladder

- V0 - pure KS (baseline in yaw_rate_pred_rads): yr = v*tan(delta)/L.
- V1 - linear-tire understeer: yr_ss = v*delta / (L + K_us*v^2).
- V2 - steering scale + offset: delta_eff = s*delta_road - delta_0.
- V3 - 1st-order yaw lag (tau ~ 50 ms) on yr_ss.

Coefficients fit on a random 60% of segments per platform with
scipy.optimize.least_squares; the other 40% are the held-out pool above.

## Inputs required
t_s, v_mps, delta_road_rad in sim_df.

## Files
- predict.py - entry point predict(sim_df, platform)
- coeffs.json - fitted per-platform coefficients
- manifest.json - declared platform support + callable path

```

## Output — STRICT JSON ONLY

No prose around it, no markdown fence. **Write it to `/Users/javiquix/Desktop/quixdev/webinar-AI/_grade/20260531-183721/self-reported/m1-agent-02.json`** using your Write tool, then return the same JSON as your final response.

```json
{
  "agent_id": "m1-agent-02",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-02/final-model/REPORT.md",
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
