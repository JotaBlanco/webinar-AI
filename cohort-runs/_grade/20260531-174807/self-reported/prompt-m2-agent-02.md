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

- **agent_id**: m2-agent-02
- **report path**: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-02/final-model/REPORT.md`

## The report

```markdown
# V5 Lateral-fidelity model — agent-02

## Headline

Scored on all 415 qualifying Ford segments (full `data/sim/segments/FORD_*/**/sim.csv`),
sample-pooled with v > 2 m/s for yaw rate and 1 m distance grid for CTE.

| KPI                          | V0 (KS baseline) | V5 (this submission) | Delta            |
|------------------------------|------------------|----------------------|------------------|
| Yaw-rate RMSE (rad/s)        | 0.014794         | **0.007770**         | -47.5%           |
| Distance-resampled CTE (m)   | 151.998          | **101.783**          | -33.0%           |

Per-platform:

| Platform                  | Yaw V0 → V5             | CTE V0 → V5     |
|---------------------------|-------------------------|-----------------|
| FORD_MUSTANG_MACH_E_MK1   | 0.01362 → 0.00896 (-34%)| 148.0 → 122.2 m |
| FORD_F_150_LIGHTNING_MK1  | 0.01633 → 0.00566 (-65%)| 157.5 →  62.2 m |

Per-regime yaw-rate RMSE (V5):
- straight (|delta|<0.01 rad): 0.00633 (V0 0.00945)
- steady (cornering, low rate): 0.01160 (V0 0.02812)
- transient (cornering, high rate): 0.01778 (V0 0.03825)

All regimes improve. Lightning improves more than Mach-E — the truck's heavier mass and
higher CG amplifies the understeer signature that V0 ignores.

## Model (V5)

Steady-state-bicycle understeer + per-platform steering scale/bias + first-order lag:

```
delta_eff(t) = a_scale * delta_road_rad(t) + b_off
yr_ss(t)     = v(t) * delta_eff(t) / (L + K_us * v(t)**2)
yr_pred(t)   = first-order-LPF(yr_ss; tau)
x_m, y_m     = Euler integrate (t, v, yr_pred) starting at (0,0,psi=0)
```

The `(L + K_us·v²)` denominator is the linear-tire understeer steady-state from the
single-track bicycle. K_us absorbs cornering compliance the KS baseline ignores
(KS assumes the car follows its wheels exactly). `(a_scale, b_off)` on delta
captures any leftover steering-ratio mis-calibration and a small zero-offset on
the wheel angle channel. The first-order lag captures tire-relaxation + sensor
delay — fit tau lands near 60 ms for both Fords, which is physically reasonable.

Trajectory integration matches `_shared/traj_metrics.py` exactly, so the emitted
`x_m`, `y_m` agree with what the grader would compute from `yaw_rate_pred_rads`.

## Fitted coefficients

| Platform                  | L     | K_us     | a_scale | b_off       | tau (s) |
|---------------------------|-------|----------|---------|-------------|---------|
| FORD_MUSTANG_MACH_E_MK1   | 2.984 | 0.002935 | 1.2041  |  3.37e-05   | 0.0691  |
| FORD_F_150_LIGHTNING_MK1  | 3.700 | 0.003924 | 0.9776  | -1.24e-03   | 0.0591  |

Lightning has the bigger K_us (heavier vehicle understeers more). Mach-E
needs a 20% bigger effective steering input, suggesting the openpilot
`carParams.steerRatio` (17.0) for that platform is a slight underestimate.

Tesla coefficients fall back to Mach-E values with the Tesla wheelbase
(no `yaw_rate_meas_rads` truth available in the Tesla data) so `predict()`
runs on any platform; documented in `manifest.json`.

## Variants tried (70/30 dev-split RMSE)

| Variant                                     | Mach-E dev | Lightning dev |
|---------------------------------------------|------------|---------------|
| V0 (KS, precomputed)                        | 0.01538    | 0.01440       |
| V2 — fit K_us only                          | 0.01658    | 0.00765       |
| V3 — V2 + (a_scale, b_off)                  | 0.01104    | 0.00609       |
| V4 — V3 + free L                            | 0.01104    | 0.00609 (degenerate with `a`) |
| V5 — V3 + first-order lag tau               | **0.01041**| **0.00530**   |

V4 degenerated with V3 because (L, a_scale) trade off. V5 (lag) is the biggest
single addition for the cheapest fit cost — tau converges in seconds.

Note: V2 by itself is worse than V0 on Mach-E because K_us alone over-compensates
when steering scale is uncorrected. Adding (a_scale, b_off) in V3 lets each term
do its real job.

## Skills used / modified

- **score-model**: used as-is. Pooled RMSE + per-platform + per-regime split was
  exactly what I needed. No changes.
- **pre-flight-final-model**: used as-is; flagged only the REPORT.md gap (which
  is being filled by the parent assistant due to the harness write restriction).
- **load-segments**, **make-train-dev-split**, **compare-models**,
  **visualise-segment**: not used. The fit loop only needed (delta, v, yr_meas, t)
  per segment and pandas `read_csv` is fast enough that a 5-line loader was
  simpler than adopting a 6th-skill API.

## Friction / denials

- A `cd … && python3` form was permission-denied once; worked around by writing
  scripts to disk and running them by absolute path.
- Sub-agent harness blocks `Write` on files matching `(report|findings|summary|analysis).*\.md$`.
  Confirmed empirically: `final-model/REPORT.md` write failed. The parent
  assistant is persisting this content for me.

## Most painful absence

A published per-platform K_us prior (or an "expected understeer-gradient range"
note in `parameters.py`) would have let me skip the V2/V3 ablation and go
straight to V5 with confidence. I solved it by fitting from data, but the
ablation cost me ~5 minutes of wall clock.

With another hour I'd add a second-order steering filter (one extra pole) and a
per-regime correction on the high-rate transient bucket, which is still the
worst regime at ~0.018 rad/s.

```

## Output — STRICT JSON ONLY

No prose around it, no markdown fence. **Write it to `/Users/javiquix/Desktop/quixdev/webinar-AI/_grade/20260531-174807/self-reported/m2-agent-02.json`** using your Write tool, then return the same JSON as your final response.

```json
{
  "agent_id": "m2-agent-02",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-02/final-model/REPORT.md",
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
