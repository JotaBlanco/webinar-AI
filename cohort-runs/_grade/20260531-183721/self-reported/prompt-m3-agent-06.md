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

- **agent_id**: m3-agent-06
- **report path**: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-06/final-model/REPORT.md`

## The report

```markdown
# agent-06 — lateral fidelity report

## Headline (scored across all 415 Ford segments, v_mps > 2 m/s filter, 1 m CTE grid)

| Metric | V0 baseline | Final (agent-06) | Delta |
|---|---|---|---|
| Yaw-rate RMSE (rad/s) | 0.01479 | **0.00742** | −49.8% |
| Distance-resampled CTE RMSE (m) | 152.00 | **89.05** | −41.4% |

Per-platform:

| Platform | V0 yr | V0 cte | Final yr | Final cte |
|---|---|---|---|---|
| FORD_F_150_LIGHTNING_MK1 | 0.01633 | 157.5 | 0.00582 | 64.2 |
| FORD_MUSTANG_MACH_E_MK1  | 0.01362 | 148.0 | 0.00836 | 103.0 |

Held-out route-split dev (seed=42, 47 routes held out / 188 total): yr=0.00808, cte=61.86. Across seeds {0, 1, 7, 42, 100} dev yr ranged 0.0080–0.0099 and dev cte 61.9–134.2 (seed=0 was a notably harder split). Train→dev gap is small enough that I'm calling this generalisation, not overfit.

Tesla: V0 passthrough — no truth channel to fit.

## What I implemented

Per-platform kinematic single-track with steady-state understeer + first-order yaw lag:

    delta_eff = g * (delta_road - delta0)
    yr_ss     = v * delta_eff / (L + K_us * v^2)
    yr_pred   = first_order_lag(yr_ss, tau)

Fitted (g, delta0, K_us, tau) per platform on 75% of routes (seed=42) via L-BFGS-B. Final per-platform coefficients (in `coeffs.json`):

- F-150 Lightning: g=1.000, δ₀=+0.00127 rad, K_us=0.00432, τ=0.060 s, L=3.70 m
- Mach-E: g=1.199, δ₀_platform=−4.2e-5 rad, K_us=0.00267, τ=0.056 s, L=2.984 m, self_δ₀_blend=0.7 (i.e. 70 % per-segment self-cal, 30 % platform)

Key Mach-E refinement: per-segment **self-calibrated δ₀** = median of `delta_road_rad` on samples with `|a_lat_meas_mps2| < 0.3` and `v_mps > 5` (interpreted as straight-line driving). Blended 70/30 with the platform-fitted δ₀. This trick uses only in-segment data — no truth peek, so it's valid at inference. It wins ~30 m of CTE on Mach-E vs platform-only δ₀ and is the single biggest improvement after the global platform fit. F-150 has a stable steering offset across segments — adding this trick hurt it, so it gets pure platform-fit δ₀.

I also tried (in `scratch/`):
- **Polynomial steering scale `g(δ) = g0 + g1·|δ|`** — marginal (dev cte 88.97 vs 90.89), not worth the param.
- **a_lat/v complementary blend with bicycle yaw** — F-150 wanted α=0, Mach-E wanted α=0.026; marginal. The a_lat signal pays off implicitly via the self-δ₀ trick instead.
- **Widened parameter bounds** — confirmed nothing was pegged.

## Skills used / modified / bypassed

- `score-model/score.py` — used as-is to confirm final figures via the same code path the grader will use.
- `pre-flight-final-model/preflight.py` — used; all 9 checks pass except `report_md_present` (sub-agent harness blocks writing REPORT.md; orchestrator persists it).
- `make-train-dev-split` — bypassed; rolled my own `route_split()` on `(platform, device, route)` tuples in `scratch/fit_and_score.py`.
- `load-segments`, `compare-models`, `visualise-segment` — not loaded; raw pandas was faster for this dataset size, and I wasn't chasing per-segment visual diagnostics within the budget.

## References consulted

- `anti-patterns.md` — read first. Directly drove three decisions:
  1. **Hold out whole routes** (not random samples) — used `(platform, device_id, route_id)` tuples for splitting.
  2. **Fit per platform**, not pooled — K_us numbers differ by 60 % (Lightning 0.00432 vs Mach-E 0.00267) so pooling would have been wrong.
  3. **Don't fit per-segment params from truth** — self-δ₀ uses only in-segment a_lat and v, no truth peek.
- `approach-menu.md` — confirmed that KS+understeer+lag is the well-explored local optimum (expected residual ~0.005–0.01 rad/s and ~80–120 m CTE; I land at 0.0074 / 89.05 m, exactly in that band). Pointed at unexplored a_lat fusion and polynomial-g paths, which I tried but didn't ship.
- `two-kpi-tradeoff.md` — diagnosed Mach-E as the bias-dominated platform (yr/cte ratio worse than F-150). The self-δ₀ trick is the explicit response: chase the bias source rather than smooth the trajectory.

## Friction / blockers

- Sub-agent harness blocks Write on `final-model/REPORT.md` ("Subagents should return findings as text, not write report files"). Workaround: full REPORT.md content returned in the agent response; orchestrator persists it manually. All other preflight checks pass.
- No other denials. `python3 + pandas + numpy + scipy` all available; fits ran in seconds.

## Most painful absence

A **k-fold or multi-seed averaged fit** rather than a single seed=42 fit. One of the 5 seeds I cross-checked gave dev cte = 134 (vs ~70 for the rest), suggesting the fit is modestly tuned to the seed=42 train routes. With more time I'd average parameters across folds, especially for Mach-E. A locked-in held-out validation route set, defined once for the cohort, would have also let me trust train→eval comparisons more directly.

```

## Output — STRICT JSON ONLY

No prose around it, no markdown fence. **Write it to `/Users/javiquix/Desktop/quixdev/webinar-AI/_grade/20260531-183721/self-reported/m3-agent-06.json`** using your Write tool, then return the same JSON as your final response.

```json
{
  "agent_id": "m3-agent-06",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-06/final-model/REPORT.md",
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
