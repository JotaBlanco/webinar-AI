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

- **agent_id**: m1-agent-01
- **report path**: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-01/final-model/REPORT.md`

## The report

```markdown
# agent-01 — lateral-fidelity submission

## TL;DR

Replaced the bare KS yaw-rate formula with a single-DOF understeer-gradient
model + first-order steering lag + small bias, fit per platform on 70% of the
shipped Ford sim segments and evaluated on the 30% held out.

| platform | KPI | V0 | ours | reduction |
|---|---|---|---|---|
| F-150 Lightning (51 files held out) | yaw RMSE [rad/s] | 0.01849 | 0.01225 | 33.7% |
| | CTE mean [m] | 74.51 | 30.03 | 60% |
| | CTE median [m] | 43.47 | 23.55 | 46% |
| Mach-E (71 files held out) | yaw RMSE [rad/s] | 0.01506 | 0.01018 | 32.4% |
| | CTE mean [m] | 78.40 | 62.98 | 20% |
| | CTE median [m] | 31.84 | 27.70 | 13% |

## Model

    tau * d(delta_eff)/dt = (alpha * delta_road + beta) - delta_eff
    psi_dot               = v * delta_eff / (L + K_us * v^2)

Trajectory is midpoint-Euler integration of (psi, x, y) from psi_dot and
measured v_mps.

## Fitted parameters

| platform | alpha | K_us [s2/m] | tau [s] | beta [rad] |
|---|---|---|---|---|
| F-150 Lightning | 0.9671 | 0.00367 | 0.078 | -0.00115 |
| Mustang Mach-E  | 1.1784 | 0.00248 | 0.083 | +2e-5    |

Notable: alpha=1.18 on the Mach-E implies the openpilot steering ratio
(17.0) is too compliant; effective rack ratio ~ 14.4. F-150 alpha=0.97 is
barely off canonical. Both vehicles fit a steering lag of ~80 ms.

## Ladder

- V0 — shipped KS baseline (tan(delta) * v / L).
- V1 — add K_us. F-150 0.0144 -> 0.0077; Mach-E barely moves.
- V2 — add alpha (effective steering-ratio scale). Mach-E 0.0166 -> 0.0110.
- V3 — add beta (steering offset). F-150 0.0076 -> 0.0061.
- V4 (shipped) — add tau first-order lag. F-150 0.0061 -> 0.0052;
                 Mach-E 0.0110 -> 0.0104.

## predict()

predict(sim_df, platform) -> DataFrame aligned with sim_df.index, columns
yaw_rate_pred_rads, x_m, y_m. Required inputs: t_s, v_mps, delta_road_rad.
Robust to NaN via ffill/bfill.

## Limitations

- Tesla unsupported. No yaw_rate_meas_rads truth in the Tesla split, so I
  declined to ship a Tesla predictor rather than guess.
- Trajectory is open-loop midpoint Euler; any residual yaw bias drifts
  linearly in arclength. A bias-correction pass was tempting but felt
  out-of-spec.
- No tyre slip / no ST rung. Understeer + lag already buys >30% on yaw RMSE.

```

## Output — STRICT JSON ONLY

No prose around it, no markdown fence. **Write it to `/Users/javiquix/Desktop/quixdev/webinar-AI/_grade/20260531-183721/self-reported/m1-agent-01.json`** using your Write tool, then return the same JSON as your final response.

```json
{
  "agent_id": "m1-agent-01",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-01/final-model/REPORT.md",
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
