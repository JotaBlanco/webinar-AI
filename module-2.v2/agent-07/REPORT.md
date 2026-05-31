# agent-07 — lateral fidelity (module 2 v2)

## Headline

| metric          | V0 baseline | shipped (V1+bv) | delta   |
|-----------------|------------:|----------------:|--------:|
| yaw_rate_rmse   |    0.012934 |        0.006809 | −47.4 % |
| cte_rmse (m)    |     163.831 |          76.550 | −53.3 % |

Scored on the full `data/sim/segments/` cohort (1996 segments, ~5.19 M samples) using `skills/score-model`. Pre-flight passes every check except `report_md_present` (the report ships separately).

## Per-platform

| platform                      | yaw_rmse | cte_rmse | yaw_bias  | cte_drift |
|-------------------------------|---------:|---------:|----------:|----------:|
| FORD_F_150_LIGHTNING_MK1      |  0.00642 |   61.810 |  −0.00100 |    −6.995 |
| FORD_MUSTANG_MACH_E_MK1       |  0.00960 |  120.719 |  +0.00055 |    +3.741 |
| HYUNDAI_IONIQ_5               |  0.00902 |  102.635 |  +0.00030 |    +0.247 |
| TESLA_MODEL_3                 |  0.00000 |    0.000 |  +0.00000 |    +0.000 |

Tesla is intentionally a V0 passthrough — its "truth" channel (`psi_dot_rads`) **is** the V0 KS output in this dataset, so any deviation increases RMSE.

## Model

Per-platform steady-state bicycle with v²-coupled understeer:

    yaw_pred = v · delta_road / (L_eff + K_us · v²)
             + bias_static
             + bias_steer  · delta_road
             + bv_steer    · v · delta_road

Five coefficients per platform (`L_eff`, `K_us`, `bias_static`, `bias_steer`, `bv_steer`). Tesla is a hard-coded passthrough.

V0 was `psi_dot = (v / L) · tan(delta_road)` — geometry only, no understeer, no per-platform calibration of bias / sensor offset, and no high-speed correction. The shipped model adds:
1. A small-angle replacement for `tan(delta)` (negligible numerically but enables (2)),
2. A v² understeer term that absorbs the steady-state tyre-slip the KS model is wrong about by construction,
3. Constant + steer-coupled bias terms (catches sensor / mounting offsets),
4. A `v · delta` term that helps explain the strong rotation-vs-speed mismatch on Mach-E (where `bias_steer` ended up at 0.12 — large by physics but small in score impact).

## Fit procedure

1. Route-grouped 85 / 15 train / dev split via deterministic seed (`make_train_dev` in `out/fit_model.py`). Same-route segments do not split.
2. Per-platform `scipy.optimize.minimize` driven by `skills/fit-model`, objective `"yaw_plus_cte"` (= `yaw_rmse + cte_rmse / 1000`), L-BFGS-B with bounded box constraints.
3. Nelder-Mead rescue pass for any platform where L-BFGS-B never moved from its initial point (Lightning's `L_eff = 3.70` init sat on a flat patch — rescue moved it to ~4.02).
4. Coefficients written to `final-model/coeffs.json`; predict reads JSON at import time.

## Variants explored

- **V0 passthrough** — baseline reference (0.01293 / 163.8).
- **V1: four-coeff bicycle (no `bv_steer`)** — single L-BFGS-B pass; got Lightning stuck on the initial flat patch. Two-pass NM+L-BFGS-B blew up because Nelder-Mead drove `gain` to ~0 (degenerate with `L_eff`); dropped `gain` from the parameter set.
- **V1 with rescue** — yaw 0.006844, CTE 76.67. Ford Lightning rescue moved L_eff 3.70 → 4.02 and reduced its CTE 130 → ~62.
- **V1 + `bv_steer` (shipped)** — yaw 0.006809, CTE 76.55. Mach-E and Hyundai pushed `bv_steer` to bounds (±0.02), suggesting more high-speed-coupled structure available, but it didn't move the score much. Pure-CTE objective gave nearly identical pooled numbers — the structural ceiling is the model class.

## Worst residual segments

The remaining error is concentrated in long, high-curvature Hyundai segments (the worst-CTE list is dominated by Hyundai routes 1.5–2 km long). On those, the per-segment yaw bias is large (e.g. `000000cc--3d3da09ecd/7`: yaw RMSE 0.114, bias −0.025), which the pooled per-platform `bias_static` cannot remove. A per-segment online-calibration step (estimate steering offset from the first N seconds of straight running) would likely help, but I had no time to implement it.

## Harness friction — most-painful absence

The **missing route / segment plotting story** hurt the most. `skills/visualise-segment` exists but is for one segment at a time; what I actually wanted was a **per-platform residual-vs-(speed, |delta|) heatmap** so I could see whether the residual structure was understeer-shaped, hysteresis-shaped, or noise-shaped. `skills/inspect-residuals` is closer but I'd have needed to bend it to plot `(v, delta)` jointly, not as separate 1-D bands. I instead inferred the understeer structure from a single ratio computation in a one-liner, which works but is brittle.

The second hurt was that the local `score-model` cannot score `data/sim-only/` (no truth column) — so I can't directly confirm that what `predict()` reads from a stripped sim_df matches the canonical grader. The pre-flight smoke run on one Mach-E sample is the only thing that catches contract drift before grading.

## Rule-driven near-misses (workshop signal)

1. I almost ran `skills/inspect-residuals` to plot vs. speed but decided not to write any plot files since the score-model dashboard already surfaced bias_fraction (≈0 after fit) — the visualisation would have been confirmation, not guidance.
2. I considered reading `webinar-meta/webinar-00-template-m3/references/approach-menu.md` for ladder advice — explicitly off-limits, so I stayed within `code/` and `_shared/` for any algorithmic hints (the `ks_model.py` docstring referencing CommonRoad's ladder was sufficient).

## Single most surprising thing

The Nelder-Mead rescue pass, when run with `gain` as a free parameter, drove `gain` to ~0.003 and `L_eff` to ~0.006 — perfectly co-degenerate, *and the loss got better*. That broke the model on test. Removing `gain` entirely (forcing the unit ratio between `delta` and `psi_dot / v`) immediately gave a stable fit. The "obvious" extra knob was actively harmful: it widened the basin of attraction for a numerically equivalent but physically nonsensical solution that the bounded L-BFGS-B polish then locked into. Sometimes fewer coefficients is the bug fix.

## Files shipped

- `final-model/predict.py` — exports `predict(sim_df, platform) -> DataFrame`.
- `final-model/coeffs.json` — per-platform fitted coefficients.
- `final-model/manifest.json` — `platform_support`, `predict_callable`.
- `out/fit_model.py` — the fit driver (reproducible).
- `out/coeffs_v2.json` — intermediate V2 coeffs from the `bv_steer` pass.
