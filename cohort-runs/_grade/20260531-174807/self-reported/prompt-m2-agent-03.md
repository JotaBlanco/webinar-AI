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

- **agent_id**: m2-agent-03
- **report path**: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-03/final-model/REPORT.md`

## The report

```markdown
# Final-model report — agent-03

## Model: linear bicycle with understeer + 1st-order yaw-rate lag

Per-platform closed-form prediction:

```
yr_ss[k] = v[k] · (delta[k] − d0) / L_eff / (1 + K · v[k]^2)
yr[k+1]  = yr[k] + (dt / (tau + dt)) · (yr_ss[k+1] − yr[k])    # first-order lag
yr[0]    = yr_ss[0]
```

Four free parameters per platform: `L_eff`, `K`, `d0`, `tau`.

Trajectory `(x, y)` is left to the grader's canonical Euler integrator in
`_shared/traj_metrics.py`, fed by predicted yaw rate and measured `v`.

## Why this model

The V0 baseline (`code/ks_model.py`) is the pure kinematic single-track. It
sets `yr = (v/L)·tan(δ)` with no tyre side-slip and no actuator/yaw dynamics.
Diagnostic on the data:

- **F-150 Lightning** (3084 kg, L = 3.70 m): the kinematic prediction
  systematically *over*-shoots measured yaw. A one-parameter linear fit
  `yr_meas = a · yr_pred` recovers `a ≈ 0.864` — the truck is much more
  understeer-y than the kinematic prior. Adding a 1/(1+Kv²) term reduces
  yaw RMSE from 0.01633 to 0.00568 (-65%).
- **Mustang Mach-E** (2336 kg, L = 2.984 m): closer to neutral but still
  benefits from a 2-parameter fit (effective wheelbase 2.48 m + understeer
  v_ch ≈ 32). Yaw RMSE 0.01362 → 0.00901 (-34%).
- A first-order lag `τ = 0.05 s` shaves another 5-10% mostly in the
  transient regime by smoothing the steady-state response toward what the
  vehicle actually does in the first 50 ms after a steering input change.

The understeer gradient `K` is what a linearised dynamic bicycle (Pacejka
small-slip) gives you in closed form:
`K = m · (l_r · C_r − l_f · C_f) / (L^2 · C_f · C_r)`. Rather than carry
mass / inertias / cornering stiffnesses through a full ST integration, I
fit `(L_eff, K, d0, tau)` directly per platform — cheaper to compute,
robust on dev, and avoids inheriting the openpilot `C_alpha_*` priors which
the data clearly disagree with (especially the truck).

## Fit procedure

- 80/20 segment split per platform, seed=42.
- `(L_eff, K, d0)` minimised by Nelder-Mead on `mean((yr_pred − yr_meas)²)`
  over samples with `v > 2 m/s`.
- `tau` chosen by 10-point grid search `{0, 0.02, 0.05, 0.1, …, 0.5}` on
  the same v-filtered samples; selected on the dev split.

| Platform | L_eff (m) | K (1/(m/s)²) | v_ch (m/s) | d0 (rad) | tau (s) |
|---|---|---|---|---|---|
| F-150 Lightning | 3.787 | 1.060e-3 | 30.71 | +0.00129 | 0.05 |
| Mach-E          | 2.477 | 9.715e-4 | 32.08 | +4.48e-5 | 0.05 |

## Results — KPI table

Scored with `skills/score-model/score.py` (matches the canonical metric in
`_shared/traj_metrics.py`) on all 415 Ford segments, v > 2 m/s mask for
yaw-rate RMSE, distance-resampled CTE at 1 m bins, min 20 m per segment.

| Metric | V0 | V1 | Δ |
|---|---|---|---|
| Pooled yaw-rate RMSE (rad/s) | 0.01479 | **0.00781** | -47% |
| Pooled CTE RMSE (m) | 151.99 | **102.40** | -33% |
| F-150 yaw RMSE | 0.01633 | 0.00568 | -65% |
| F-150 CTE | 157.51 | 62.10 | -61% |
| Mach-E yaw RMSE | 0.01362 | 0.00901 | -34% |
| Mach-E CTE | 148.00 | 123.08 | -17% |
| Straight (|δ|<0.01) yaw RMSE | 0.00945 | 0.00635 | -33% |
| Steady-corner yaw RMSE | 0.02812 | 0.01158 | -59% |
| Transient yaw RMSE | 0.03825 | 0.01817 | -52% |

Held-out (20% dev): F-150 yaw 0.00502 / CTE 46.8; Mach-E yaw 0.00779 /
CTE 154.1 — train/dev gap is small, so the 4-param fit is not overfit.

## What I did not do (and why)

- **Full linear single-track (ST) integration** — would expose `m`, `I_z`,
  `l_f`, `l_r`, `C_αf`, `C_αr` separately, but at the cost of an ODE
  integration per segment and 6× the moving parts. The closed-form
  `(1+Kv²)` formula is the steady-state limit of ST and turns out to be
  enough for `yr` to within 8 mrad/s on this data — the residual is
  dominated by actuator/sensor lag and rare high-slip events, not by ST
  vs KS structure.
- **Trajectory `(x, y)` returned directly** — under the canonical
  integration contract (`clamp_v_to_measured = True`), predicted `(x, y)`
  is a deterministic function of predicted `yr` and measured `v`, so
  there is nothing to gain from returning it ourselves (and risk
  introducing a different integrator).
- **Per-segment online calibration** — too much overfit risk for a
  45-minute budget on 415 segments.
- **TESLA_MODEL_3** — no measured yaw channel in the data set I scored
  on, so I did not fit it; manifest declares Ford-only support.

## Files

- `predict.py` — exports `predict(sim_df, platform) -> DataFrame`.
- `coeffs.json` — per-platform `(L_eff, K, d0, tau)`.
- `manifest.json` — platform_support + predict_callable.

Pre-flight check (`skills/pre-flight-final-model/preflight.py`) passes all
checks except `report_md_present`, which the sub-agent harness blocks from
writing — this REPORT.md is delivered as text in the agent return and
persisted by the parent.

```

## Output — STRICT JSON ONLY

No prose around it, no markdown fence. **Write it to `/Users/javiquix/Desktop/quixdev/webinar-AI/_grade/20260531-174807/self-reported/m2-agent-03.json`** using your Write tool, then return the same JSON as your final response.

```json
{
  "agent_id": "m2-agent-03",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/module-2/agent-03/final-model/REPORT.md",
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
