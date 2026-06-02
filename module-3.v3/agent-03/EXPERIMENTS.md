# EXPERIMENTS.md

Append-only log of attempts. One entry per concrete attempt.

## Alternatives considered

Considered (≥5; ≥3 structural):

- (structure) **residual_gb** — V1 + per-platform gradient-boosted tree residual head over input features. Attacks the non-linear transient-regime residual that V1's single-pole lag mis-shapes.
- (structure) **residual_learner** — V1 + linear ridge head over 11 input features. Attacks the same residual but with linear capacity, to baseline non-linearity.
- (structure) **lead_compensator** — V1 with a steering-rate lead term `K_d · d_delta/dt` injected into the steady-state input. Targets transient regime via a single parametric knob.
- (structure) **dynamic_st** — linear dynamic single-track (vy, yr) ODE with backward-Euler integration. Rung-1 climb past V0/V1's kinematic shape; targets transient-slip dynamics.
- (refines-v1) **v1_refit** — Nelder-Mead refit of V1's 6 parameters per platform. Sanity-check that V1 is already near its parameter ceiling.

---

## E00 — V1 baseline

- Hypothesis: V1 is the pre-shipped rung-0 ceiling. Score it to confirm the floor.
- Result (full sim/segments): pooled yaw 0.01061 rad/s; CTE 75.65 m.
  - Per-platform: Lightning yaw 0.01273 / CTE 62.18; Mach-E yaw 0.01363 / CTE 98.68;
    Ioniq-5 yaw 0.00893 / CTE 69.53; Tesla 0/0 (passthrough).
- Verdict: baseline.

## E01 — Diagnose V1 residual

- Hypothesis: structural attacks should be guided by *what* V1 mis-fits.
- What I did: computed regime-share of residual sum-of-squares across (transient `|d_delta|>0.05`, high-`|a_lat|` proxy, straight) bins, and Pearson correlations of residual with input features (`out/diagnose.py`).
- Result:
  - Transient regime carries 44% (Lightning) / 30% (Mach-E) / 34% (Ioniq) of yaw RMSE² despite being 3-5% of rows.
  - High-`|a_lat|` is <1% of total residual everywhere — tyre saturation not the issue here.
  - Residual correlates with `delta` (corr -0.21 on Lightning/Mach-E), `yr_v0` (-0.13 on Mach-E), and only weakly with `d_delta` itself — signal is non-linear in those features.
- Verdict: keep. Points at non-linear transient residual; rules out tyre saturation as the dominant attack surface.

## E02 — residual_learner (linear ridge)

- Model dir: models/residual_learner/
- Hypothesis: a small linear correction over input features can recover the obvious linear part of V1's residual.
- What I did: ridge-regression over 11 allowlist features, per platform (`out/fit_residual.py`).
- Result: pooled yaw 0.01061 → 0.01043 (-1.7%); CTE 75.65 → 72.35 (-4.4%).
  - Per-platform R²: 5% / 5% / 2%.
- Verdict: shelve. Low R² confirms the residual is non-linear. Useful as a structural baseline.

## E03 — lead_compensator (single extra parametric knob)

- Model dir: models/lead_compensator/
- Hypothesis: a steering-rate lead `K_d · d_delta/dt` inside V1's ss formula recovers the transient gain.
- What I did: jointly refit `(g, L_eff, K_us, tau, K_d, delta0)` per platform with NM.
- Result: pooled yaw 0.01061 → 0.01053 (-0.8%); CTE 75.65 → 75.33 (~unchanged).
  - Optimiser drove `K_d < 0` and `tau ≈ 0.01` on every platform — wants to anticipate steering rather than smooth it.
- Verdict: shelve. One extra linear knob is not enough; the residual is non-linear in cross-products of (delta, d_delta, v).

## E04 — v1_refit (refines-v1 control)

- Model dir: models/v1_refit/
- Hypothesis: maybe V1's published coefficients are not at the parameter optimum on this data.
- What I did: NM refit of 6 V1 params per platform.
- Result: Lightning 0.01273 → 0.01268 (-0.4%); Ioniq 0.00893 → 0.00889 (-0.5%); Mach-E hit a degenerate optimum (`L_eff -> 0.5`) — kept original.
- Verdict: shelve. Confirms V1 is near its parameter ceiling; structural change is the only path past it.

## E05 — residual_gb (gradient boosted residual)

- Model dir: models/residual_gb/
- Hypothesis: residual is non-linear (E02 + E03 evidence); tree ensemble over input features should capture it.
- What I did: `HistGradientBoostingRegressor(max_iter=200, max_depth=5, lr=0.05, min_samples_leaf=200, l2=1e-3)` per platform on residual `yr_truth - yr_v1`, features `[delta, d_delta, v, yr_v0, yr_v1, v·yr_v0, a_long]`.
- Result: pooled yaw 0.01061 → 0.00743 (-30.0%); CTE 75.65 → 59.44 (-21.4%). Per-platform R² on residual: 0.68 / 0.74 / 0.27.
- Held-out check: route-grouped 80/20 split per platform; held-out yaw 2-13% better than V1, held-out CTE 14-51% better than V1 — generalises.
- Verdict: ship. Structurally novel from V1 (non-linear, learned, sample-wise head); both KPIs improved both in-sample and out-of-route.

## E06 — dynamic_st (abandoned)

- Model dir: models/dynamic_st/
- Hypothesis: linear dynamic single-track ODE is the principled rung-1 climb past V0/V1's kinematic shape.
- What I did: wrote backward-Euler integrator over (vy, yr) state, parameterised by `(g_steer, C_af, C_ar, Iz_mul)`, NM-fitted on yaw RMSE per platform. Single forward eval ≈ 0.15 s for Lightning.
- Result: NM optimiser on the Ioniq platform (84 routes, 2.3M rows) did not finish inside the 45-minute budget — killed after ~10 min wall-clock with no per-iter progress emitted (NM was inside `minimize` without callbacks). Lightning and Mach-E never got past the first platform.
- Verdict: shelved within budget. Not a structural negative — just optimiser-too-slow + missing per-segment caching of `predict_dyn`. With more budget would re-attempt with parallel-segment vectorisation or scipy `least_squares` on stacked residual vector.
