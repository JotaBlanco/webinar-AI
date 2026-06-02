# REPORT — module-3.v3 / agent-02 (lateral-fidelity)

See `../REPORT.md` for the full report. This file mirrors it.

## Headline numerical result (sim-only/segments/ dev set; full 3.5M samples, 1215 segments)

| model | pooled yaw RMSE (rad/s) | pooled CTE RMSE (m) | Δ vs V1 |
|---|---|---|---|
| V1 baseline (code/v1_baseline.py)        | 0.01061 | 75.65 | — |
| affine post-correction                    | 0.01053 | 72.53 | yaw -0.7%, CTE -4.1% |
| saturation correction                     | 0.01053 | 72.61 | yaw -0.7%, CTE -4.0% |
| **v1-plus-residual-features (SHIPPED)**   | **0.01052** | **72.61** | **yaw -0.9%, CTE -4.0%** |

Per-platform signed-CTE drift (the headline structural win):
- Mach-E: -21.98 m → -1.84 m
- IONIQ-5: -11.57 m → -4.20 m
- Lightning: +0.32 m → -3.80 m (small over-correction)

## What I implemented (3 candidate models)

1. `models/affine-postcorrection/` — `yr = a*yr_v1 + b` per platform.
2. `models/saturation-correction/` — adds `c * yr_v1 * (v*yr_v1)²` cubic.
3. `models/v1-plus-residual-features/` (shipped) — combined affine + saturation + steering-rate.

## Most painful absence

A **route-grouped train/dev split** discipline forced by the harness — `make-train-dev-split/` was present but nothing made me use it. My OLS coefficients are in-sample; no generalisation-gap estimate.

## Almost-did, rules prevented

Reflexively wanted to fit on `a_lat_meas_mps2` — truth-leak (a_lat = v * yr_truth). Substituted `v * yr_v1`.

## Single most surprising thing

Cubic saturation feature was visually striking in residual bin plots but added essentially zero on top of the affine `a` — linear OLS already absorbed the variance. Bin-wise plots can lie about regression headroom.
