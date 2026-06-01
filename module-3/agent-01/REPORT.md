# Module 3 Agent 01 — Lateral fidelity REPORT

## Headline

| Metric | V0 baseline | Shipped | Δ |
|---|---|---|---|
| Pooled yaw_rate_rmse (rad/s) | 0.012934 | **0.005874** | −54.6% |
| Pooled cte_rmse (m) | 163.83 | **56.81** | −65.3% |

Scored locally with `skills/score-model` over all four platforms on `data/sim/segments/` (the same allowlist contract the canonical grader uses).

### Per platform

| Platform | yaw_rmse | cte_rmse | n_segments |
|---|---|---|---|
| FORD_F_150_LIGHTNING_MK1 | 0.00566 | 62.19 | 175 |
| FORD_MUSTANG_MACH_E_MK1 | 0.00859 | 98.68 | 240 |
| HYUNDAI_IONIQ_5 | 0.00766 | 69.54 | 800 |
| TESLA_MODEL_3 (passthrough) | 0.00000 | 0.00 | 781 |

## Model

Per-platform kinematic bicycle with steady-state understeer and a first-order yaw-rate lag, plus a platform-gated per-segment steering-offset correction:

```
δ_eff = (δ_road − δ₀) · g
yr_ss = v · δ_eff / (L_eff + K_us · v²)
yr[k] = yr[k−1] + (dt/(τ+dt)) · (yr_ss[k] − yr[k−1])
```

`δ₀` per segment is estimated from the segment's own straight-driving rows
(gated on `|yaw_rate_pred_rads| < 0.03 ∧ v > 5 m/s`, falling back to a
platform-wide constant when fewer than 50 rows qualify). The gate uses V0's
yaw-rate prediction as the straightness proxy because the
`a_lat_meas_mps2` channel that the doc recipe uses is **not in the
operating-contract allowlist** — it gets stripped before predict() sees it.

Tesla has no independent truth channel, so it passes V0 through unchanged.

### Coefficients

| Param | Lightning | Mach-E | Hyundai |
|---|---|---|---|
| g | 0.863 | 0.891 | 0.93817 |
| L_eff | 3.26 | 2.22 | 2.8871 |
| K_us | 0.00350 | 0.00150 | 0.0028925 |
| τ (s) | 0.060 | 0.069 | 0.061895 |
| δ₀ fallback | 0.00133 | −0.0001 | 0.0 |
| per-segment δ₀ | OFF | ON | ON |

Lightning + Mach-E priors are from `references/anti-patterns.md` (prior
top-performing recipe). Mach-E K_us was retuned 0.002 → 0.0015 by grid
sweep (CTE 101.2 → 98.7). Hyundai was fit fresh with `skills/fit-model`
(L-BFGS-B, `yaw_plus_cte` objective, 60/20 train/dev seg split).

## Exploration log

See `EXPERIMENTS.md` for full E00–E05 + FINAL entries. Five structurally
distinct candidates considered before committing (per
`references/exploration-discipline.md` rule):
1. Recipe replay with priors (chosen route).
2. Rung-1 linear dynamic single-track with slip angles.
3. Residual learner on physical prior.
4. Complementary filter fusing V0 with `a_lat/v` as an alternative yaw
   estimate.
5. Per-regime mixture model.

Routes 2–5 were left on the bench: route 1 cleared most of the gap in one
move, and the residual shape (straight + steady regimes carrying meaningful
absolute error, not just transient) didn't argue for climbing a rung yet.

## What I noticed

- The recipe's `a_lat_meas_mps2` gate **fails silently** under the scoring
  allowlist. The `score-model` skill strips it before predict() is called.
  I almost shipped a `KeyError` at grading time.
- `fit-model` on Mach-E pushed K_us toward 0 and made both metrics worse vs
  the published priors — the cohort priors had more information than the
  50-segment fit. Lesson: don't re-fit a platform whose published prior is
  already close to optimal on a tiny sample budget.
- The Mach-E worst-CTE route (`00000000--33439c2a9c`, 5 contiguous
  segments ~340 m CTE each) shares a single signed direction (−240 m
  mean). That's a route-level systematic, not segment noise — addressing
  it might need either a richer per-segment δ₀ rule (more straight-row
  coverage on tight-cornering routes) or climbing to a dynamic
  single-track model.

## Harness gaps that cost me time

- No `inspect-residuals` invocation in my loop — I hand-sweep coefficients
  with print()s. A structured "Δ-CTE per segment between V1 and V3" view
  from `compare-models` would have flagged that Mach-E was the residual
  faster.
- The two reference docs `anti-patterns.md` and `approach-menu.md` gave
  the recipe + the exact prior coefficients for two platforms. That's the
  *whole reason* I hit −65% CTE in well under budget. Without those docs I
  would have spent the entire 45 minutes re-deriving.

## Deliverable contract

- `final-model/predict.py:predict(sim_df, platform)` ✓
- `final-model/manifest.json` with `platform_support`, `predict_callable` ✓
- `final-model/coeffs.json` ✓
- predict.py verified end-to-end on a sim-only segment from each of the 4
  platforms (allowlist-stripped input, no truth columns).
