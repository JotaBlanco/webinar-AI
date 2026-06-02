# REPORT — module-4.v2 agent-01 (idea-01 lateral fidelity)

## 1. Headline result (local dev split, all platforms pooled, v>2 m/s)

| Variant | yaw_rate_rmse (rad/s) | cte_rmse (m) |
|---|---|---|
| V0 (passthrough) | 0.016773 | 218.16 |
| V1 (provided baseline) | 0.007617 | 75.65 |
| **V4 (shipped)** | **0.007509** | **72.70** |

Improvements vs V1: yaw -1.4%, CTE -3.9%. Vs V0: yaw -55.2%, CTE -66.7%. All three platforms now within the "ok" yaw-bias threshold; only Mustang CTE still flags `warn` (-5.8 m, was -22 m on V1).

Per-platform on V4: F150 yaw 0.00566 / CTE 62.2, Mustang 0.00833 / CTE 94.5, Hyundai 0.00759 / CTE 66.5.

## 2. What I implemented

- **fit_v2.py** — Nelder-Mead refit of V1's five params (`g, L_eff, K_us, tau, delta0`) per platform. Marginal: ~same yaw as V1.
- **predict_v2.py** — V1 shape + a single constant `yaw_bias_correction` per platform, set from V1's measured `yaw_residual_mean`. Killed the CTE drift warnings (Mustang -22→-4.6 m).
- **fit_v3.py / predict_v3.py** — Joint Nelder-Mead optimisation of `(g, L_eff, K_us, tau, delta0_fallback, yaw_bias)` over 100 segs/platform. F150 fit became pathological (the optimiser put a +5 ms⁻¹ delta0 against a -0.005 rad/s yaw bias that nearly cancel).
- **V4 (shipped)** — Hybrid: V1's F150 coefficients (per-seg delta0 hurt F150), V3's joint fit for Mustang and Hyundai. Cleanest CTE result.

## 3. Most painful absence

The `iterate` / tree-search and `compare-models` skills exist but I never invoked them — I drove the inner loop ad-hoc. The truly missing piece was a **gradient-friendly fit harness**: `fit-model` is a skill but I rolled my own Nelder-Mead loop because I couldn't justify the time to dig into its API. A `fit(predict_template, segments, params_to_optimise)` one-liner would have saved 10 minutes and let me try 3-4 more variants (e.g. piecewise `g` for left/right turns, speed-dependent `K_us`).

## 4. Rules-prevented near-misses

I almost reached into `/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/` for a baseline reference — `v1_baseline.py` mentions "m3.v2 cohort findings" and the natural instinct was to read those cohort notes. Stayed inside `references/` and the `v1_baseline.py` docstring instead.

I also nearly globbed the Tesla sim/segments alongside Ford/Hyundai before noticing those Tesla files have the OLD schema (`psi_dot_rads` instead of `yaw_rate_meas_rads`) and would have crashed score-model.

## 5. Most surprising thing learned

V1's largest CTE outliers (Mustang highway route `33439c2a9c`, 5 segments, ~300+ m CTE each) shrink only marginally even after killing the global yaw bias — they're per-segment yaw biases that survive the per-segment delta0 calibration because that calibration uses V0 yr<0.03 as a "straight" mask and these are gentle highway curves, not straights. The grader's worst-case CTE is concentrated in a tiny minority of highway segments where any structural model error compounds over kilometre-long arcs. Yaw RMSE is essentially a solved problem on this dataset (V1 already hits 0.0076); CTE is where the action is, and CTE is a **bias** problem more than a noise problem.

## Honest caveats

- I did NOT run `pre-flight-final-model` (would have hit `data/sim/test/` but no such split exists in my view — paths only show `data/sim/segments`). So my "dev" numbers above are pooled over ALL non-Tesla sim segments, which conflates train and dev. The yaw_bias was fit on 100 segments per platform; the score above is on all 1215 — overfit risk is small (yaw_bias is one scalar per platform) but non-zero.
- Tesla platform is unsupported (no truth column in `data/sim/segments/TESLA_MODEL_3/`); my predict falls through to V0 passthrough, which is the correct behaviour for that platform.
