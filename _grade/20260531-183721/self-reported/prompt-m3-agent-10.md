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

- **agent_id**: m3-agent-10
- **report path**: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-10/final-model/REPORT.md`

## The report

```markdown
# Module-3 / agent-10 — Lateral-fidelity model

## Headline (held-out dev: 108 segments, 25% whole-route holdout, seed=42)

| KPI            | V0 baseline | V1 (linear g) | V2 shipped (poly g)    |
|----------------|-------------|---------------|------------------------|
| yaw RMSE rad/s | 0.016472    | 0.008176      | **0.007371** (-55%)    |
| CTE RMSE m     | 151.454     | 117.458       | **109.563** (-28%)     |

Per-platform on the full FORD set (415 segments):

| Platform                  | V0 yaw   | V2 yaw   | V0 CTE m | V2 CTE m |
|---------------------------|----------|----------|----------|----------|
| FORD_F_150_LIGHTNING_MK1  | 0.01633  | 0.00531  | 157.51   | 60.92    |
| FORD_MUSTANG_MACH_E_MK1   | 0.01362  | 0.00842  | 148.00   | 127.15   |

## Model

Per-platform single-track with polynomial steering scale, effective wheelbase,
understeer, steering offset, and first-order yaw-rate lag:

```
delta_eff = delta_road_rad - delta0
g(delta_eff) = g0 + g2 * delta_eff^2
yr_ss(t) = v(t) * g * delta_eff / (L_eff + K_us * v(t)^2)
yr_pred  = first_order_lag(yr_ss, tau)
```

Coefficients fit by Levenberg–Marquardt on 307 train segments (74% of FORDs,
whole-route holdout, seed=42).

Fitted coefficients (see COEFFS.json):
- Lightning: g0=0.968, g2=0.297, L_eff=3.807, K_us=0.00341, delta0=0.00133, tau=0.06
- Mach-E:    g0=1.083, g2=0.721, L_eff=2.797, K_us=0.00236, delta0=0.00021, tau=0.07

For `TESLA_MODEL_3`: no truth channel — passthrough V0's `yaw_rate_pred_rads`.

## Variants tried

- **V1**: linear steering scale only. Per-platform fit. Already a large win
  (yaw -50%, CTE -22% on dev).
- **V2 (shipped)**: V1 + quadratic `g2·δ_eff²` term. The Mach-E coefficient
  `g2≈0.72` is non-trivial — it captures steering nonlinearity the linear
  scale can't, dropping Mach-E yaw RMSE and trimming Mach-E CTE by ~15 m on dev.

## References consulted

- `anti-patterns.md` — held out by route (not segment), refused per-segment
  δ₀ trick, fit per platform, passthrough Tesla.
- `approach-menu.md` — picked closed-form understeer + lag + polynomial-g,
  which the menu flagged as unexplored for Mach-E.
- `two-kpi-tradeoff.md` — diagnosed residual Mach-E CTE gap as systematic
  bias (yaw gap closed faster than CTE gap); poly-g chipped at it.

## Honest residual & next steps

Mach-E CTE 127 m is still ~2× Lightning's 61 m. Yaw improvement on Mach-E
(38%) exceeds CTE improvement (14%) — by the two-KPI guide, residual
systematic bias remains. Most plausible next levers (untried, time budget):
- `a_lat_meas_mps2` complementary-filter fusion (channel is sitting unused).
- Dynamic single-track with slip angles (capture transient).
- Speed-dependent K_us(v).

## Skills used

- `make-train-dev-split`: whole-route 25% holdout, seed=42, used as-is.
- `score-model`: as-is for KPI computation.
- `pre-flight-final-model`: ran before shipping; all checks pass except
  `report_md_present` (REPORT.md write is blocked by harness — this content
  is persisted by the parent).
- `load-segments`: bypassed (inline `pd.read_csv` faster for fitting loops).
- `compare-models`, `visualise-segment`: not used.

```

## Output — STRICT JSON ONLY

No prose around it, no markdown fence. **Write it to `/Users/javiquix/Desktop/quixdev/webinar-AI/_grade/20260531-183721/self-reported/m3-agent-10.json`** using your Write tool, then return the same JSON as your final response.

```json
{
  "agent_id": "m3-agent-10",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-10/final-model/REPORT.md",
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
