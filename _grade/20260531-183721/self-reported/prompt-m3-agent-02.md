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

- **agent_id**: m3-agent-02
- **report path**: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-02/final-model/REPORT.md`

## The report

```markdown
# agent-02 — Lateral Fidelity Final Report

## Headline numbers (DEV, whole-route held-out, seed=42, PYTHONHASHSEED=0)

| KPI                   | V0       | Final (V5) | Delta  |
|-----------------------|---------:|-----------:|-------:|
| Yaw-rate RMSE (rad/s) | 0.01407  | 0.00758    | -46.1% |
| CTE RMSE (m)          | 163.75   | 117.71     | -28.1% |

Per-platform on DEV (Final V5):

| Platform                   | yaw RMSE  | CTE RMSE  |
|----------------------------|----------:|----------:|
| FORD_F_150_LIGHTNING_MK1   | 0.00640   |  79.69 m  |
| FORD_MUSTANG_MACH_E_MK1    | 0.00821   | 135.22 m  |

Per-regime yaw RMSE (Final V5, DEV): straight 0.00717, steady 0.00963, transient 0.01010.

Held-out evaluation uses whole-route hold-out (no segments-from-same-route on both sides), 25% routes per platform on DEV, 75% on TRAIN — 106 dev segments, 309 train. The dev/train split is sensitive to `PYTHONHASHSEED` (the split skill XORs `seed` with Python's randomised `hash(platform)`); all numbers above use `PYTHONHASHSEED=0`.

## Model class (V5, shipped)

Per-platform extended kinematic single-track:

- Polynomial steering scale: `g(δ) = g0 + g2 · δ²`
- Speed-dependent understeer: `K(v) = K0 + K1 · v`
- Constant steering offset: `δ0`
- First-order yaw-rate lag with time constant `τ`
- Per-segment steering-offset removal from `a_lat`-derived "going-straight" rows (|a_lat| < 0.3 m/s², v > 5 m/s, ≥100 samples; median of `delta_road` on those rows, capped to ±0.02 rad)

Steady-state form:
`yr_ss(t) = v · (g(δ_corr) · δ_corr + δ0) / (L + K(v) · v²)`

Transient form (Euler discretisation of first-order lag):
`yr_pred[k+1] = yr_pred[k] + (dt[k]/τ) · (yr_ss[k] - yr_pred[k])`

Tesla: V0 passthrough (no `yaw_rate_meas_rads` in `sim.csv`; fitting infeasible per anti-patterns brief).

## Coefficients (fit on TRAIN only, 309 segments)

| Platform                  | g0    | g2    | δ0      | K0      | K1        | τ      | L     |
|---------------------------|------:|------:|--------:|--------:|----------:|-------:|------:|
| FORD_F_150_LIGHTNING_MK1  | 0.955 | 0.310 | -0.0012 | 0.00473 | -4.65e-05 | 0.0632 | 3.70  |
| FORD_MUSTANG_MACH_E_MK1   | 1.151 | 0.876 |  0.0003 | 0.00259 | -1.64e-05 | 0.0739 | 2.984 |

`L` is the openpilot-canonical wheelbase from `code/parameters.py`. Wheelbase was not co-fit (would absorb degeneracy with K_us). Mach-E `g0 = 1.15` ≠ 1.0 reflects steering-scale calibration the upstream V0 leaves on the table; the `g2 ≈ 0.88` polynomial term captures Mach-E's clear nonlinear understeer signature.

## Variants tried and why V5

- V0 (passthrough): DEV yaw 0.01407, CTE 163.75.
- V1: per-platform `g, δ0, K_us, τ`. DEV yaw 0.00832 (-41%), CTE 144.80 (-12%). Big yaw gain, small CTE gain — classic "residual systematic bias" signature per the two-KPI-tradeoff doc.
- V2: V1 + polynomial `g(δ)` + `a_lat` complementary fusion fit jointly. Optimiser pegged α=0 (joint MSE fit didn't reward a_lat fusion). Mach-E DEV CTE regressed. Dropped.
- V3: V1 + `g(δ)=g0+g2·δ²` + `K_us(v)=K0+K1·v`. DEV yaw 0.00752, CTE 144.15. Diagnostic showed Mach-E DEV CTE was dominated by ~10 long routes (1500-2000 distance bins each) where tiny persistent heading-rate bias compounded into hundreds of metres.
- V4: V3 + per-segment yaw bias correction from `a_lat`-derived yaw. Regressed both KPIs — `a_lat / v` is too noisy to set a global yaw bias. Dropped.
- V5 (shipped): V3 + per-segment steering-offset removal. Use `a_lat` as a "going-straight" indicator and take the median measured `delta_road` on those rows as the per-segment steering centring offset; subtract from `delta` before feeding into the physics. Refit all params on offset-corrected TRAIN. DEV yaw 0.00758, CTE 117.71. Mach-E DEV CTE 177 → 135 (-24%); F-150 DEV CTE 58 → 80 m (slight regression — the offset trick is calibrated on Mach-E-dominated mixed loss, F-150 has less true offset; acceptable because pooled CTE improves substantially).

## How the references shaped this

- `anti-patterns.md` forced: whole-route hold-out (used `make-train-dev-split` skill), per-platform fitting, and the constraint that any per-segment correction must be derivable from input channels alone (V5's offset estimator uses only `delta`, `v`, `a_lat`).
- `approach-menu.md` flagged polynomial `g`, speed-dependent `K_us`, and `a_lat` fusion as unexplored. Two of the three (polynomial g, K_us(v)) helped; joint a_lat fusion did not. The reference did **not** suggest using a_lat as a straight-line detector; that emerged from interpreting V3's residual structure.
- `two-kpi-tradeoff.md` correctly diagnosed V1→V3 as having residual systematic bias (yaw gains much bigger than CTE gains) and pointed at the steering-offset cause. Without it I'd have plausibly chased noise-reduction approaches.

## Limits and caveats

- The fit objective is sample-pooled yaw MSE on TRAIN. CTE isn't directly optimised. A heading-drift regulariser (`lam_drift` in `work/fit_v3.py`) was prototyped but the shipped V5 uses `lam_drift=0`.
- Per-segment offset estimator falls back to 0 if a segment has fewer than 100 qualifying "going-straight" samples — conservative on short segments.
- DEV vs TRAIN gap on Mach-E CTE remains visible (74 m vs 135 m). My DEV contains a small cluster of very long held-out routes where any residual bias amplifies; I've kept it visible rather than truncating it away.
- Tesla support is V0 passthrough only.
- `predict.py` is fully self-contained: numpy + pandas, coefficients loaded from sibling `coeffs.json`. Pre-flight passes all checks (modulo the REPORT.md presence check, which depends on this file being persisted by the parent).

```

## Output — STRICT JSON ONLY

No prose around it, no markdown fence. **Write it to `/Users/javiquix/Desktop/quixdev/webinar-AI/_grade/20260531-183721/self-reported/m3-agent-02.json`** using your Write tool, then return the same JSON as your final response.

```json
{
  "agent_id": "m3-agent-02",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-02/final-model/REPORT.md",
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
