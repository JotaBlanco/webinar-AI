# REPORT — module-2.v2 / agent-08 — lateral fidelity

## Headline

Pooled, across all 1,996 segments (~5.2 M samples) on `data/sim/segments/`:

| metric | V0 baseline | final model (V2) | reduction |
|---|---|---|---|
| **yaw_rate_rmse (rad/s)** | 0.012934 | **0.006459** | -50.1% |
| **cte_rmse (m)**          | 163.83 | **76.61** | -53.2% |

All per-platform signed-bias warnings cleared (yaw bias ≤ 0.65 mrad/s, CTE drift ≤ 2.8 m vs V0's +39.7 m and -54.8 m on F-150 and Hyundai respectively). Tesla is held at V0 identity (since `psi_dot_rads` IS the V0 KS output — deviating could only inflate RMSE).

Per-platform yaw / CTE RMSE after fit:
- FORD_F_150_LIGHTNING_MK1: 0.00576 / 60.73 m  (V0: 0.01633 / 157.5 m)
- FORD_MUSTANG_MACH_E_MK1:  0.00901 / 120.69 m (V0: 0.01362 / 148.0 m)
- HYUNDAI_IONIQ_5:          0.00864 / 102.92 m (V0: 0.01770 / 247.5 m)
- TESLA_MODEL_3:            0.00000 / 0.00 m   (identity)

## What I implemented

Two variants, both per-platform scalings of the V0 KS baseline `yv0` (kept Tesla pinned to identity throughout):

1. **V1 — understeer-corrected V0 with bias.** `yaw_pred = (G·yv0)/(1 + Kus·v²) + bias`. Three coefficients per platform, fit with `skills/fit-model` against the `yaw_plus_cte` blend (cte_weight=2.0, L-BFGS-B, bounds). Result: yaw 0.00684, CTE 76.56. Cleared bias warnings on both Fords and Hyundai.

2. **V2 (shipped) — V1 plus first-order lag + yaw-rate damping.** Adds two coefficients per platform: `tau` (low-pass time constant on `yv0`) and `kdot` (coefficient on `d yv0 / dt`). Five coeffs per platform. Result: yaw 0.00646, CTE 76.61. The lag mainly helped the transient regime (yaw RMSE 0.0200 → 0.0165 in `transient`).

Marginal CTE gain over V1 was zero — the remaining CTE budget is dominated by ~12 Hyundai segments whose signed CTE is -250 to -700 m even at <0.025 rad/s yaw RMSE. That is route-/segment-specific drift, not something a global per-platform calibration can absorb.

## Most painful missing component

A **per-route or per-segment grouping layer** in `fit-model` / `score-model`. The bias-warnings dashboard clearly fingerprints route-level systematic offsets on Hyundai (one direction of drift on virtually every long highway segment in the worst-CTE list), but the fitter only buckets by platform. With a `fit_by_route` or even a quick `route_bias` calibration tool I'd have eaten a big chunk of the remaining 100 m CTE on Hyundai. `inspect-residuals` would have helped me see this faster too — I had to hand-roll a residual analyser in `out/residual_analysis.py` to confirm the asymmetric sign pattern in `yv0 > 0.05` vs `yv0 < -0.05`. That two-line skill being absent cost ~10 minutes.

## Rule-violations narrowly averted

I almost ran the score-model on `data/sim-only/segments/` directly to "verify the grader path", then realised sim-only has no truth column and the local scorer would either error or silently report zero — and reaching for the canonical grader files (in `/Users/javiquix/Desktop/quixdev/webinar-AI/_grade`) was right there in my head as the "obvious" next move. Forbidden. Stuck to the local scorer on `sim/`, preflight on `sim-only/`.

I also briefly considered peeking at `module-2/` for prior coefficient priors. Resisted.

## Most surprising thing learned

The signed-residual asymmetry by `yv0` sign on all three platforms — `yv0 > 0.05` had negative residual, `yv0 < -0.05` had positive residual. I expected one understeer gain to dominate. Instead the residual pattern says the V0's `tan(δ)` is *overshooting* in magnitude in BOTH turn directions. The cure isn't sign-asymmetric — it's a sub-unity gain modulated by `v²`, which is exactly the Kus understeer term I bolted on. But seeing the data confess it that cleanly before I picked the model was nice.

## Honest failures

- V2 over V1 was a wash on CTE. The lag/damping was the wrong knob — what's left isn't model-shape, it's per-route bias. Shipping V2 anyway because yaw improved marginally and it costs nothing at predict-time.
- I didn't split train/dev. With ~1,996 segments and 5 params/platform that's defensible but not principled.
- I did not engage skills `compare-models`, `visualise-segment`, `make-train-dev-split`, `load-segments`, or `inspect-residuals`. The first two were unnecessary (I trusted the scorer's worst-N tables); the last three would have been useful but I rolled my own.

## Files

- `final-model/predict.py` — `predict(sim_df, platform) -> DataFrame` with `yaw_rate_pred_rads, x_m, y_m`.
- `final-model/manifest.json` / `final-model/coeffs.json`
- `out/fit_v1.py` (V1 fit + score)
- `out/fit_v2.py` (V2 fit + score, produced `coeffs_v2.json`)
- `out/residual_analysis.py` (per-bin signed-residual probe)
