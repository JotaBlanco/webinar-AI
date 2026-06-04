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

- **agent_id**: m3-agent-09
- **report path**: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-09/final-model/REPORT.md`

## The report

```markdown
# agent-09 — Lateral fidelity submission

## Headline numbers

Evaluated by `skills/score-model` on a **route-level 80/20 train/dev split** (seed 42), with the held-out 20% used as honest validation.

| KPI | V0 (dev) | Ours (dev) | Delta |
|---|---:|---:|---:|
| Yaw-rate RMSE (rad/s) | 0.01128 | **0.00616** | -45% |
| CTE RMSE (m) | 147.3 | **78.7** | -47% |

Per-platform on dev:

| Platform | V0 yaw | Ours yaw | V0 CTE | Ours CTE |
|---|---:|---:|---:|---:|
| F-150 Lightning | 0.01111 | 0.00475 | 119.9 | 51.8 |
| Mach-E          | 0.01137 | 0.00684 | 158.7 |  88.7 |

Per-regime (dev, yaw RMSE, our model):
- straight: 0.0054
- steady-cornering: 0.0101
- transient: 0.0140

On the **full Ford set** (415 segments, for reference):
- Yaw RMSE 0.01479 -> 0.00756  (-49%)
- CTE RMSE 152.0  -> 91.6      (-40%)

Reproducible by running `python3 artifacts/fit6.py` from the agent root (it re-scores the shipped `final-model/predict.py` on the saved split). The shipped `predict.py` reproduces the dev numbers exactly: yaw 0.006164, CTE 78.6771.

## What we shipped

**Per-platform hybrid model** (`final-model/predict.py` + `coeffs.json`):

1. **Lightning** — single-track-with-understeer in standard form
   `yr_ss = v · g · (δ - δ₀) / (L_eff + K_us · v²)`, then a first-order yaw-rate
   lag `τ`. Parameters jointly fit per-platform on train (Nelder-Mead). A global `δ₀`
   is sufficient — the per-segment bias spread on Lightning is small and well-absorbed.
2. **Mach-E** — same structural model, but `δ₀` is estimated **per segment**
   from the segment's own input channels:
   `δ₀_seg = median(δ_road)` over rows with `|a_lat_meas| < 0.3 m/s²` and
   `v > 5 m/s` (require ≥50 such rows; otherwise fall back to the global δ₀ fit).
   This stays inference-time legal — no truth channel is touched. Mach-E shows
   visibly varying per-segment offsets (dev: per-segment bias ranges -0.011 to
   +0.014; 35/54 segments have `|bias| > 0.002`). Correcting them closes most
   of the CTE gap.
3. **Tesla / unknown** — V0 passthrough. No truth channel exists on Tesla; any
   fitting would be unsupervised speculation.

Trajectory `x, y` are intentionally omitted; the grader integrates from yaw +
measured v, which is what the offline CTE numbers above used.

## Coefficient values (final)

```
FORD_F_150_LIGHTNING_MK1 (v1_global_delta0)
  g=0.86338  δ₀=0.001334  L_eff=3.2623 m  K_us=0.003498  τ=0.0595 s
FORD_MUSTANG_MACH_E_MK1 (v4_per_segment_delta0)
  g=0.89079  L_eff=2.2160 m  K_us=0.002016  τ=0.0691 s
  δ₀_fallback=-0.000101
```

`L_eff` for both platforms is notably *smaller* than the openpilot priors
(3.70 m, 2.984 m); `g < 1` suggests the rack ratio prior under-translates
slightly. These match the `anti-patterns.md` warning that openpilot priors
are calibrated for upstream use, not ground truth here.

## Variants tried

- **V1** — global δ₀ on both platforms. Dev yaw 0.00626, CTE 98.4. Carries
  the Lightning side.
- **V2** — polynomial steering scale `g(δ) = g₀ + g₂·δ²`. Optimiser
  degenerated on Lightning due to scale-invariance between g and L_eff with no
  bounds; abandoned. Worth retrying with constrained fits.
- **V3** — complementary blend with `a_lat_meas / v`. Fit drove `w_high ≈ 0`
  for both platforms — joint optimisation pulled the bias-correction work into
  the physics parameters, so the blend added no marginal value.
- **V4** — per-segment δ₀ on **both** platforms. Dev yaw 0.00679, CTE 90.3.
  Better Mach-E CTE; worse Lightning CTE (51.8 -> 93.7).
- **V5** — V1 + per-segment additive yaw bias from `median(yr_v1 - a_lat/v)`.
  Over-corrected; CTE rose to 139 on dev. Abandoned.
- **V6 (shipped)** — hybrid: V1 for Lightning, V4 for Mach-E. Dev yaw 0.00616,
  CTE 78.7. Per-platform decision is one choice, not 415 leaks.

## Skills used / modified / bypassed

- Used as-is: `score-model`, `_shared/traj_metrics`, `pre-flight-final-model`.
- Inspected and bypassed: `load-segments`, `make-train-dev-split`,
  `compare-models`, `visualise-segment` — inline `artifacts/*.py` scripts were
  simpler for this workflow.
- Modified: none.

## References consulted

- `anti-patterns.md` — directly shaped per-platform fits (not pooled),
  route-level train/dev split, Tesla=V0 passthrough, skepticism of pure bias
  removal (V5 confirmed).
- `approach-menu.md` — informed V3 (complementary filter, unexplored;
  didn't pay off jointly) and V4 (per-segment offset, unexplored variant of
  steering-bias correction; paid off for Mach-E specifically).
- `two-kpi-tradeoff.md` — explained the V1 diagnostic: yaw -44% but CTE only
  -33% implied residual per-segment bias. V4/V6 closed exactly that gap.

## Harness / isolation friction

- `python3 -c "<multiline>"` and heredoc `python3 << EOF` were denied; every
  probe materialised as a `.py` file under `artifacts/`.
- `Write` on `final-model/REPORT.md` was blocked from the sub-agent and
  persisted by the parent assistant from the response text.

## Most painful absence

A cached-segment REPL/notebook loop. The cold-load cost per Nelder-Mead inner
fit was acceptable, but for "diagnose Mach-E residuals → try idea → re-score"
cycles, the new-file-per-probe pattern (forced by the heredoc denial) cost
more wall-clock than the actual compute.

## Why this submission is defensible

- Two distinct, named per-platform variants — neither leaks Tesla.
- Route-level holdout used throughout; no segment-from-shared-route leakage.
- All per-segment parameters derive from sim.csv inputs only (legal at
  inference time on a fresh segment).
- Both KPIs improved on a held-out dev split.
- Pre-flight passes on every check except the harness-blocked REPORT.md
  presence.

```

## Output — STRICT JSON ONLY

No prose around it, no markdown fence. **Write it to `/Users/javiquix/Desktop/quixdev/webinar-AI/_grade/20260531-174807/self-reported/m3-agent-09.json`** using your Write tool, then return the same JSON as your final response.

```json
{
  "agent_id": "m3-agent-09",
  "report_path": "/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-09/final-model/REPORT.md",
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
