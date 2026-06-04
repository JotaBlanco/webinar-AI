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

- **agent_id**: m2-agent-10
- **report path**: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-10/final-model/REPORT.md`

## The report

```markdown
# Lateral fidelity — agent-10 final model

## Headline numbers (full Ford eval set, scored with `skills/score-model`)

| KPI                              | V0 (baseline) | V1 (this model) | Improvement |
|----------------------------------|---------------|-----------------|-------------|
| Yaw-rate RMSE (rad/s)            | 0.01479       | 0.00770         | -48 %       |
| Distance-resampled CTE RMSE (m)  | 151.998       | 102.324         | -33 %       |

Per platform (all 415 segments):

| Platform                    | V0 yaw RMSE | V1 yaw RMSE | V0 CTE  | V1 CTE  |
|-----------------------------|-------------|-------------|---------|---------|
| FORD_F_150_LIGHTNING_MK1    | 0.01633     | 0.00547     | 157.5 m | 63.7 m  |
| FORD_MUSTANG_MACH_E_MK1     | 0.01362     | 0.00894     | 148.0 m | 122.4 m |

Per regime (yaw RMSE, v > 2 m/s): straight 0.0094 → 0.0063; steady 0.0281 → 0.0115; transient 0.0382 → 0.0175.

Honest dev-set check (25% whole-route hold-out, seed=42): V1 dev yaw 0.00743 vs V0 dev yaw 0.01506; dev CTE 68 m vs V0 dev CTE 174 m. Train/dev coefficients agreed within ~1% on K, tau, s; b0 was identical to four significant figures. No overfit detected.

## Model

For each platform p, with measured `t, v, delta`:

1. Low-pass the steering input on the (non-uniform) time grid:
   `delta_f[k] = (1 - a[k]) * delta_f[k-1] + a[k] * delta[k]`, where `a[k] = dt[k] / (tau_p + dt[k])`.
2. Yaw rate: `psi_dot = s_p * (v * delta_f) / (L_p + K_p * v^2) + b0_p`.

This is the steady-state linear-bicycle yaw rate (kinematic single-track + understeer term `K * v^2`), modulated by a global steering gain `s` (absorbs steering-ratio mismatch, sidewall compliance, and the `tan(delta)≈delta` approximation error in V0) plus a constant offset `b0` (sensor / mounting bias).

Coefficients (least-squares fit on full data, grid (K, tau) × closed-form (s, b0)):

| Platform                  | L     | K       | tau    | s       | b0          |
|---------------------------|-------|---------|--------|---------|-------------|
| FORD_MUSTANG_MACH_E_MK1   | 2.984 | 0.00275 | 0.060  | 1.1931  | +2.19e-4    |
| FORD_F_150_LIGHTNING_MK1  | 3.700 | 0.00375 | 0.060  | 0.9693  | -4.44e-3    |

Notes:
- Mach-E `s ≈ 1.19` says V0 under-predicts yaw by ~19% — consistent with V0 using kinematic geometry where the real rack/sidewall combo turns sharper.
- F-150 `b0 ≈ -4.4 mrad/s` (~-0.25 deg/s) is a real, segment-pooled yaw-rate offset (sensor bias or mounting yaw). Removing it alone closes most of the F-150 gap.
- `tau = 60 ms` on both platforms — a tight first-order lag on the steering channel is the only dynamics that the bicycle form misses. Setting tau = 0 costs ~3% on yaw RMSE; not big, but consistent across train/dev.

## Variants tried

1. **V0** baseline (kinematic single-track, precomputed): RMSE 0.01479 / CTE 152 m. Reference.
2. **V1 understeer + scale + bias (no lag)**: yaw 0.00779, CTE 103 m. Big single-step gain.
3. **V1 + first-order lag (tau grid-search)** — *shipped*: yaw 0.00770, CTE 102.3 m. Marginal but consistent.
4. **V2 cubic-in-feature** (tire saturation): train -3% vs V1, dev *worse*. Dropped.
5. **V3 speed-scaled steering gain** (`s + sv·v`): train -3%, dev flat. Less interpretable. Dropped.
6. **V4 full bilinear** in (v, feat, feat³): same overfit signal — dev worse than V1. Dropped.

V1 was the Pareto winner across train, dev, and the full set.

## Skills

- Used: `score-model/score` (both KPIs on full and dev; the only score I trusted); `make-train-dev-split/split` (whole-route hold-out); `pre-flight-final-model/preflight` (final shipping check — passes apart from the REPORT.md write block).
- Inspected, not used: `load-segments`, `compare-models`, `visualise-segment` — train/dev metrics were sufficient signal.
- No skill modified.

## Friction notes

- Bash permission denial on ad-hoc shell commands (`python -c`, `ls *.py`) forced all exploration through small scripts under `_work/`. Python execution itself was unrestricted.
- `final-model/REPORT.md` write was blocked by the sub-agent harness (filename matches `report.*\.md`); this content was returned to the parent for persistence.

## Most painful absence

A vectorised one-pole low-pass helper. The time-varying-coefficient recursion over ~1M samples in pure-Python `for` loops dominated every fit-and-score iteration. A `scipy.signal.lfilter`-style wrapper handling `alpha[k] = dt[k]/(tau + dt[k])` would have cut grid-search wall-clock ~10x and let me explore richer variants honestly.

```

## Output — STRICT JSON ONLY

No prose around it, no markdown fence. **Write it to `/Users/javiquix/Desktop/quixdev/webinar-AI/_grade/20260531-174807/self-reported/m2-agent-10.json`** using your Write tool, then return the same JSON as your final response.

```json
{
  "agent_id": "m2-agent-10",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-10/final-model/REPORT.md",
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
