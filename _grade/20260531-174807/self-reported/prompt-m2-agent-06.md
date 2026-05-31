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

- **agent_id**: m2-agent-06
- **report path**: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-06/final-model/REPORT.md`

## The report

```markdown
# agent-06 — Lateral-Fidelity Report

## Model

**V2 = KS kinematic + steady-state understeer + first-order steering lag.**

For every sample on a segment:

```
delta_f(t) = lowpass( delta_road(t), tau )                       # first-order LP
yr(t)      = scale · (v / L) · tan( delta_f(t) - delta0 ) / (1 + K · v²)
x, y       = forward-Euler integration of (v, yr) from (0, 0, psi=0)
```

Four physical effects, one per coefficient:

| Coef     | Captures                                                  |
|----------|-----------------------------------------------------------|
| `K`      | Steady-state understeer (linear bicycle limit)            |
| `delta0` | Steering-system zero / sensor-alignment bias              |
| `scale`  | Residual yaw gain (steering-ratio / Ackermann mismatch)   |
| `tau`    | First-order driver/EPS lag on steering input              |

Per-platform fitted coefficients (held-out train split, seed=42, dev=25%, v>2 m/s):

| Platform                     | L      | tau   | K       | delta0  | scale   |
|------------------------------|--------|-------|---------|---------|---------|
| FORD_F_150_LIGHTNING_MK1     | 3.700  | 0.06  | 9.0e-4  | 0.0012  | 0.93203 |
| FORD_MUSTANG_MACH_E_MK1      | 2.984  | 0.06  | 8.8e-4  | 0.0000  | 1.17364 |
| TESLA_MODEL_3 (no truth)     | 2.875  | 0.06  | 8.0e-4  | 0.0000  | 1.00000 |

Tesla coefficients are defensive defaults — there is no `yaw_rate_meas_rads`
channel on Tesla rlogs, so the model can't be fitted; values are nominal.

## Headline numbers (canonical `score-model` skill, Ford segments only)

V0 = baseline `yaw_rate_pred_rads` already present in `sim.csv` (KS, v-clamped, δ-clamped).

| Slice           | Yaw RMSE V0 → V2          | CTE RMSE V0 → V2          |
|-----------------|---------------------------|---------------------------|
| ALL (415 segs)  | 0.01479 → **0.00732** (−51%) | 152.00 → **101.96** (−33%) |
| DEV (114 segs)  | 0.01465 → **0.00674** (−54%) | 154.38 → **119.23** (−23%) |
| TRAIN (301 segs)| 0.01485 → **0.00753** (−49%) | 151.15 →  **95.13** (−37%) |

Per-platform on ALL:

| Platform                     | Yaw V0 → V2           | CTE V0 → V2          |
|------------------------------|-----------------------|----------------------|
| FORD_F_150_LIGHTNING_MK1     | 0.01633 → 0.00523     | 157.51 → 61.49       |
| FORD_MUSTANG_MACH_E_MK1      | 0.01362 → 0.00849     | 148.00 → 122.66      |

Per-regime yaw RMSE on ALL (rad/s):

| Regime    | V0       | V2       |
|-----------|----------|----------|
| straight  | 0.00945  | 0.00631  |
| steady    | 0.02812  | 0.01010  |
| transient | 0.03825  | 0.01530  |

Train and dev are within ~10% of each other — no meaningful overfit.

## Why these coefficients move the metric so much

- The Lightning is a heavy, high-CG truck with a long wheelbase; KS over-predicts
  its yaw at speed by a large margin. `K ≈ 9e-4` and `scale ≈ 0.93` together
  catch the dominant understeer gradient and the sensor-side gain mismatch.
- The Mach-E is closer to a passenger car; its `scale > 1` says KS *under*-predicts
  yaw at the reported road-wheel angle — almost certainly a steering-ratio bias
  in the openpilot carParams (i_s = 17.0 may be slightly high for this trim).
- `tau ≈ 60 ms` is what most production EPS racks ship for command-to-rack delay;
  it makes the biggest mark on the *transient* yaw bin and on CTE (which
  integrates errors over distance).

## Pipeline / process

- Train/dev split: skill `make-train-dev-split`, whole-route holdout, seed=42,
  dev_fraction=0.25, stratified by platform.
- Fit: grid + refine over (K, δ0, scale) at each candidate `tau ∈ {0, 0.03, 0.05, 0.06, 0.08, 0.10, 0.15}`;
  scale solved in closed form at each grid point. Best (tau, K, δ0, scale) selected by train MSE.
- Scoring: skill `score-model` (canonical CTE math from `_shared/traj_metrics.py`).
- Bundle validated end-to-end by skill `pre-flight-final-model` — every check passes.

## Files shipped

- `final-model/predict.py` — model V2 with lag + understeer + bias + scale.
- `final-model/coeffs.json` — per-platform coefficients (consumed by `predict.py`).
- `final-model/manifest.json` — `platform_support`, `predict_callable`.
- `final-model/REPORT.md` — this file.

```

## Output — STRICT JSON ONLY

No prose around it, no markdown fence. **Write it to `/Users/javiquix/Desktop/quixdev/webinar-AI/_grade/20260531-174807/self-reported/m2-agent-06.json`** using your Write tool, then return the same JSON as your final response.

```json
{
  "agent_id": "m2-agent-06",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-06/final-model/REPORT.md",
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
