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

- **agent_id**: m2-agent-09
- **report path**: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-09/final-model/REPORT.md`

## The report

```markdown
# Agent-09 lateral fidelity model — REPORT

## Headline results

Scored across all 415 Ford segments under `data/sim/segments/FORD_*` using
`skills/score-model/score.py` (sample-pooled yaw-rate RMSE with v > 2 m/s
filter; segment-then-bin-pooled CTE at 1 m grid step, min 20 m per segment).

| metric                | V0 baseline | Final model | improvement |
|-----------------------|-------------|-------------|-------------|
| yaw-rate RMSE (rad/s) |     0.01479 |     0.00773 |    -47.7 %  |
| CTE RMSE (m)          |    151.998  |    102.086  |    -32.8 %  |

Per-platform:

| platform                    | V0 yr   | Final yr | V0 cte | Final cte |
|-----------------------------|---------|----------|--------|-----------|
| FORD_MUSTANG_MACH_E_MK1     | 0.01362 | 0.00895  | 148.00 | 121.99    |
| FORD_F_150_LIGHTNING_MK1    | 0.01633 | 0.00555  | 157.51 |  63.87    |

Per-regime yaw-rate RMSE (final): straight 0.00628, steady 0.01163, transient 0.01763.

Held-out 80/20 split (seed=42): coefficients converged to the same values on
the train-only fit; dev-only yaw-rate RMSE 0.00791 vs 0.00773 on the full
set — generalisation is clean.

## What I implemented

Steady-state yaw rate from a linear bicycle with understeer gradient:

    yr_ss(t) = v(t) * (s * delta_road(t)) / (L + K * v(t)^2) + bias

driven through a first-order lag (time-constant tau) plus an integer sample
delay d (typically 0-1 samples on this 50 Hz data):

    delayed_ss[i] = yr_ss[i - d]                    # clamped at the start
    yr[i]         = (1 - a) * yr[i-1] + a * delayed_ss[i-1],   a = dt / (tau + dt)

Coefficients fit per platform on all 415 segments via scipy Nelder-Mead on
yaw-rate MSE (samples with v > 2 m/s). Integer delay swept on outer loop.

Fitted values (final shipped):
- Mach-E:    s = 1.2033, K = 0.00294, bias = +0.000214, tau = 0.032 s, delay = 1
- Lightning: s = 0.9773, K = 0.00392, bias = -0.00442,  tau = 0.023 s, delay = 1

The Mach-E `s = 1.20` is striking — `delta_road_rad` for the Mach-E appears
~17 % under-scaled vs what reproduces measured yaw rate. Lightning is at
s ≈ 1.0. Likely a steering-ratio / adapter quirk.

predict() also returns x_m / y_m, integrated identically to
`_shared/traj_metrics.integrate_trajectory` using measured v and the
predicted yaw rate.

## Skills usage

- `score-model/score.py` — used as-is, every iteration.
- `pre-flight-final-model/preflight.py` — ran before shipping; passes all
  checks except `report_md_present` (REPORT.md write is blocked in the
  sub-agent and is persisted by the parent).
- `make-train-dev-split/` — bypassed (inline numpy permutation, trivial).
- `load-segments/`, `compare-models/`, `visualise-segment/` — not loaded;
  pandas + the scorer covered the workflow.

## Variants tried

- **V1** (bicycle + understeer + per-platform scale + bias, no lag):
  YR 0.00844 / CTE 101.50. Most of the headline improvement comes from this.
- **V2** (V1 + first-order lag): YR 0.00774 / CTE 102.58. Lag hits
  transients (regime YR 0.0240 → 0.0178) but barely moves CTE since CTE is
  dominated by low-frequency angular error accumulation.
- **V3 shipped** (V2 + integer-sample input delay d): essentially identical
  to V2; delay 0-1 chosen per platform. Marginal Mach-E benefit.

## Residual structure (what's left)

- Symmetric residual std ~0.008 rad/s (Mach-E), ~0.005 rad/s (Lightning) —
  no obvious |delta| or v dependence inside the fit range.
- Mild high-speed (v > 30 m/s) bias of ~+0.002 rad/s on both platforms,
  suggesting the v² understeer term doesn't quite cover high-speed dynamics.
- Small left/right asymmetry in residual mean (~±0.001 rad/s) — visible but
  too small to justify directional coefficients.

## What I didn't try (and why)

- **Per-segment bias correction from yaw_rate_meas in sim_df**: would have
  helped CTE further but is reading the truth channel from the input — judged
  as bleeding the metric.
- **Full linear ST with Pacejka slip dynamics**: the understeer scalar K
  already captures the steady-state contribution; the marginal complexity
  didn't fit the budget.
- **Higher-order velocity terms** for the >30 m/s residual.
- **Per-turn-direction coefficients** for the small left/right asymmetry.

```

## Output — STRICT JSON ONLY

No prose around it, no markdown fence. **Write it to `/Users/javiquix/Desktop/quixdev/webinar-AI/_grade/20260531-183721/self-reported/m2-agent-09.json`** using your Write tool, then return the same JSON as your final response.

```json
{
  "agent_id": "m2-agent-09",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-09/final-model/REPORT.md",
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
