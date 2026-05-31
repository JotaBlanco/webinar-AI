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

- **agent_id**: m3-agent-01
- **report path**: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-01/final-model/REPORT.md`

## The report

```markdown
# Lateral-fidelity report — agent-01

## TL;DR

A per-platform kinematic-bicycle steady-state yaw model with a first-order
lag, fit on 75% route-holdout train data, cuts both KPIs significantly vs V0
on the held-out dev split:

| KPI | V0 (dev) | Final (dev) | Δ |
|---|---|---|---|
| yaw-rate RMSE (rad/s) | 0.01316 | 0.00837 | **−36.4%** |
| CTE RMSE (m) | 117.44 | 93.05 | **−20.8%** |

On the full FORD pool (415 segments, what the grader is likely to use):

| KPI | V0 | Final | Δ |
|---|---|---|---|
| yaw-rate RMSE (rad/s) | 0.01479 | 0.00802 | **−45.8%** |
| CTE RMSE (m) | 151.99 | 105.47 | **−30.6%** |

Per-platform on full data: Lightning gets the bigger win (yaw −63%, CTE −57%); Mach-E is the residual problem (yaw −33%, CTE −15%).

## Model

For each Ford platform:

```
yr_ss(t) = v(t) * g * (delta(t) - delta_0) / (L + K_us * v(t)^2)
yr_pred  = first-order low-pass of yr_ss with tau = 0.08 s
x_m, y_m = forward-Euler integration with measured v and predicted yr
```

Tesla has no `yaw_rate_meas_rads` truth channel and is not fit. For Tesla
segments, `predict()` passes through the sim.csv's existing `yaw_rate_pred_rads`
(the V0 KS prediction) and the V0 x/y if present.

### Fitted coefficients (training set, route-holdout)

| Platform | g | K_us | delta_0 (rad) | L (m) | Fit method |
|---|---|---|---|---|---|
| FORD_F_150_LIGHTNING_MK1 | 0.9567 | 0.00338 | 0.000846 | 3.70 | two-stage |
| FORD_MUSTANG_MACH_E_MK1 | 1.1726 | 0.00252 | 0.000139 | 2.984 | joint LS |

- *Joint LS*: simultaneous least-squares on `(g, K_us, delta_0)` minimising sample-pooled `(yr_pred − yr_meas)` with `v > 5 m/s`.
- *Two-stage*: `delta_0 = mean(delta)` on straight rows (`|yr_meas| < 0.003`); then `(g, K_us)` fit with `delta_0` fixed.
- No bound was pegged. Note `g_MachE > 1`, consistent with a steer-ratio scale slightly under-estimated by the openpilot prior; `g_Lightning < 1` the opposite.

The hybrid (Lightning two-stage, Mach-E joint) was chosen because each performed best on its own platform on the dev split. The CTE gap between methods is ~7m on Lightning and ~20m on Mach-E.

## Variants tried (and why discarded)

1. **Polynomial steering `g(δ) = g₀ + g₂·δ²`** — improved yaw RMSE by ~10% on both platforms but Mach-E CTE rose from ~113 to ~123 m. The reference doc `two-kpi-tradeoff.md` flagged this as the "wins yaw, loses CTE" pattern: a small steady-state bias in the polynomial coefficients drifts the trajectory even when sample-pooled RMSE looks fine. Dropped.
2. **Complementary fusion with `a_lat_meas/v`** — fit a linear blend `(a, b, c)` such that `yr_pred = a·yr_model + b·(a_lat/v) + c`. Helped yaw marginally (-1% over V1) but blew up CTE (132 → 132 then 165 on Mach-E). The lateral-accel sensor carries enough noise to corrupt the integration. Dropped.
3. **Two-stage on Mach-E** — small improvement to Mach-E CTE (89 vs 113 in one earlier run, but inconsistent across splits due to a separate bug — see below). On the deterministic split, joint LS edged out two-stage for Mach-E.

## Anti-patterns observed and avoided

- **Per-segment bias removal** — not used. The references called it a floor not a ceiling; my numbers above are achieved by physical-parameter fitting, not bias subtraction.
- **Fit on one platform, ship for both** — explicitly avoided; each platform has its own `(g, K_us, δ₀)` and each fit method was chosen per platform.
- **Random sample-level train/dev splits** — avoided; the `make-train-dev-split` skill holds out whole `(platform, device, route)` tuples.
- **Tesla coefficients by analogy** — avoided; passthrough.

## Bug found in `make-train-dev-split`

The shipped skill used Python's built-in `hash(platform)` to derive a per-platform seed:

```python
pool_seed = seed ^ (hash(platform) & 0xFFFFFFFF)
```

`hash()` for strings is salted per Python process by default (PYTHONHASHSEED=random), so the train/dev split was different on every run. This silently produced different coefficient fits and ~7-15% variation in dev CTE between identical-looking runs. Replaced with `hashlib.sha256(platform.encode()).digest()` for a stable hash. Diff is in `skills/make-train-dev-split/split.py`.

This is the only skill modification made.

## What I would do with more time

1. **Mach-E transient regime**: the dynamic single-track (linear bicycle with slip angles) is unexplored on this data. The transient-regime yaw RMSE is 0.0191 rad/s on the full set, ~3x the straight regime. That's where the remaining CTE on Mach-E lives.
2. **Held-out test set**: I tuned on a single 75/25 split; a second untouched holdout would tell me whether MBA-mixed-fit truly generalises or just got lucky.
3. **Per-platform tau**: the lag time constant was assumed equal across platforms. Lightning may benefit from a longer tau given its much heavier rotational inertia (`I_z` ~ 2.5x Mach-E).

## Files

- `predict.py` — exports `predict(sim_df, platform)`.
- `coeffs.json` — fitted parameters and tau.
- `manifest.json` — `platform_support`, `predict_callable`.

Pre-flight: 8/9 checks pass; only `report_md_present` fails because the
sub-agent harness blocks `Write` on `*report.md` patterns. The report content
is included verbatim in the agent's response so the parent can persist it.

```

## Output — STRICT JSON ONLY

No prose around it, no markdown fence. **Write it to `/Users/javiquix/Desktop/quixdev/webinar-AI/_grade/20260531-174807/self-reported/m3-agent-01.json`** using your Write tool, then return the same JSON as your final response.

```json
{
  "agent_id": "m3-agent-01",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-01/final-model/REPORT.md",
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
