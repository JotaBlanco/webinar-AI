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

- **agent_id**: m1-agent-05
- **report path**: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-05/final-model/REPORT.md`

## The report

```markdown
# agent-05 — lateral-fidelity submission

## Headline numbers (held-out validation, 30% deterministic split by file hash)

| Platform | KPI | V0 baseline | V1 (this submission) | Improvement |
|---|---|---|---|---|
| FORD_MUSTANG_MACH_E_MK1 | Yaw-rate RMSE (rad/s) | 0.01197 | 0.00870 | -27.3% |
| FORD_MUSTANG_MACH_E_MK1 | CTE RMSE (m, 1 m grid) | 83.89 | 67.19 | -19.9% |
| FORD_F_150_LIGHTNING_MK1 | Yaw-rate RMSE (rad/s) | 0.01269 | 0.00694 | -45.3% |
| FORD_F_150_LIGHTNING_MK1 | CTE RMSE (m, 1 m grid) | 51.81 | 33.83 | -34.7% |
| TESLA_MODEL_3 | — | — | V0 fallback (no truth) | — |

CTE truth = `yaw_rate_meas_rads` integrated against `v_mps`. The CSV `x_m, y_m`
columns are V0's own integrated trajectory and cannot serve as ground truth.

## Model ladder

- V0 baseline: `psi_dot = (v / L) * tan(delta)`.
- V1 shipped: `psi_dot = gain * v * (delta - delta_offset) / (L + Kus * v^2)`
  — linear-bicycle / understeer-gradient form. Three scalars per platform,
  fit by Nelder-Mead on yaw-rate RMSE vs `yaw_rate_meas_rads` on the full pool.

Speed-bucket diagnostics showed V0 residual decreasing monotonically with v —
the classic understeer signature — so V1 was the natural step up from a
plain gain or steering-offset-only correction.

### Shipped coefficients

| Platform | L (m) | Kus | delta_offset (rad) | gain |
|---|---|---|---|---|
| FORD_MUSTANG_MACH_E_MK1 | 2.984 | 0.00256 | -3.5e-05 | 1.1775 |
| FORD_F_150_LIGHTNING_MK1 | 3.700 | 0.00344 | 0.00122 | 0.9567 |
| TESLA_MODEL_3 | 2.875 | 0 | 0 | 1.0 |

Mach-E gain 1.18 is suspicious — likely steer-ratio overestimate or column
compliance. Either way, the fit absorbs it.

## Isolation notes
Did not read other agents' work, orchestrator material, or raw rlogs.
Worked entirely from sim CSVs and `code/`.

```

## Output — STRICT JSON ONLY

No prose around it, no markdown fence. **Write it to `/Users/javiquix/Desktop/quixdev/webinar-AI/_grade/20260531-183721/self-reported/m1-agent-05.json`** using your Write tool, then return the same JSON as your final response.

```json
{
  "agent_id": "m1-agent-05",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-05/final-model/REPORT.md",
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
