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

- **agent_id**: m2-agent-05
- **report path**: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-05/final-model/REPORT.md`

## The report

```markdown
# Agent-05 — Lateral Fidelity, Module 2

## Approach

Two layers of correction over the V0 kinematic single-track model, both speed-known and per-platform:

1. **Understeer-corrected linear bicycle** (steady-state form):
   `yr = g · v · (δ − δ₀) / (L + K_us · v²)`
   - `g` corrects the steering-ratio scale that openpilot's `carParams.steerRatio` misses (notably ~19 % under-reporting on the Mach-E).
   - `K_us` injects the speed-dependent understeer the pure kinematic model ignores.
   - `δ₀` absorbs a small static toe/alignment offset (~1 mrad on the F-150 Lightning).
2. **First-order steering+tire lag** with per-platform time constant τ (~55 ms), applied as a dt-aware causal LPF on the bicycle yaw rate. This captures the lumped actuator and sidewall compliance the kinematic model doesn't have. Biggest win is in the transient regime.

Parameters were fitted by Nelder-Mead on a 75/25 whole-route, platform-stratified split (seed 42) using sample-pooled MSE on yaw-rate, masked to `v_mps > 2`.

Coefficients (final, in `coeffs.json`):

| Platform | L (m) | g | K_us | δ₀ (rad) | τ (s) |
|---|---|---|---|---|---|
| FORD_MUSTANG_MACH_E_MK1 | 2.984 | 1.2124 | 0.00302 | −0.00018 | 0.0585 |
| FORD_F_150_LIGHTNING_MK1 | 3.700 | 0.9784 | 0.00395 | 0.00134 | 0.0525 |
| TESLA_MODEL_3 (untrained fallback) | 2.875 | 1.000 | 0.00300 | 0.00000 | 0.0500 |

## Results

Whole-route, platform-stratified split (seed=42). Dev = 108 of 415 segments (truly held out).

| Model | DEV yr-RMSE | DEV CTE-RMSE | TRAIN yr-RMSE | TRAIN CTE-RMSE |
|---|---|---|---|---|
| V0 baseline | 0.01308 | 129.06 | 0.01536 | 158.31 |
| V1 (bicycle, no lag) | 0.00890 | 91.87 | 0.00823 | 104.15 |
| **V2 (bicycle + lag, shipped)** | **0.00851** | **92.32** | **0.00755** | **104.25** |

Per-platform DEV (V0 → V2):
- FORD_F_150_LIGHTNING_MK1: yr 0.0125 → 0.0052; CTE 127.4 → 63.8
- FORD_MUSTANG_MACH_E_MK1: yr 0.0136 → 0.0105; CTE 130.7 → 113.5

Per-regime DEV yr-RMSE (V0 → V2): straight 0.0086 → 0.0066; steady 0.0250 → 0.0137; transient 0.0360 → 0.0219.

## What I didn't ship

- Full dynamic (ST/linear-bicycle) state-space with side-slip — overkill for the data; calibrated linear bicycle hits diminishing returns and would risk instability without speed-conditioned damping.
- Mach-E gap (CTE still 113 m) likely comes from non-linear steering-ratio variation with steering angle. A second-order polynomial in δ for g(δ) or a small lookup table could close it; ran out of budget.
- No bank-angle or road-grade correction — `a_lat_meas_mps2` would be a hint but isn't in the truth channel set.

## Files

- `predict.py` — exposes `predict(sim_df, platform) -> DataFrame` with `yaw_rate_pred_rads`, `x_m`, `y_m`.
- `coeffs.json` — per-platform calibrated (L, g, K_us, δ₀, τ).
- `manifest.json` — `platform_support`, `predict_callable = "predict.py:predict"`.

Preflight: all checks pass (sample segment round-trips clean).

```

## Output — STRICT JSON ONLY

No prose around it, no markdown fence. **Write it to `/Users/javiquix/Desktop/quixdev/webinar-AI/_grade/20260531-174807/self-reported/m2-agent-05.json`** using your Write tool, then return the same JSON as your final response.

```json
{
  "agent_id": "m2-agent-05",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-05/final-model/REPORT.md",
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
