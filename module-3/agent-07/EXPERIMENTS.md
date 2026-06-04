# EXPERIMENTS.md

Append-only log of approaches tried.

## E00 — V0 baseline (no changes)
- Rung: 0
- Hypothesis: establish the floor we're trying to beat.
- What I changed vs nothing: nothing — predict() passes through `yaw_rate_pred_rads`.
- Result (full sim/): yaw 0.012934 rad/s; CTE 163.83 m.
  - per-platform: Lightning yaw 0.01633 cte 157.5; Mach-E yaw 0.01362 cte 148.0; Hyundai yaw 0.01770 cte 247.5.
  - signed bias: Lightning +39.7 m drift, Hyundai -54.8 m drift (both flagged 🚨).
- Verdict: baseline.

## E01 — Recipe: KS + understeer + lag + per-segment δ₀, platform-gated
- Rung: 0
- Hypothesis: anti-patterns.md identifies this as THE highest-leverage move (the "legal cousin"). Per-segment δ₀ estimated from straight-driving rows using the V0 yaw-rate gate (allowlist-only).
- What I changed vs E00: shipped the recipe verbatim from references/anti-patterns.md § "The legal cousin" with the prior top-tier coefficient set. Per-segment δ₀ ON for Mach-E and Hyundai, OFF for Lightning (uses global δ₀). Tesla unchanged (V0 passthrough).
- Result (full sim/): yaw 0.005874 rad/s (-54.6%); CTE 56.81 m (-65.3%).
  - per-platform: Lightning yaw 0.00566 cte 62.2; Mach-E yaw 0.00859 cte 98.7; Hyundai yaw 0.00766 cte 69.5.
  - signed bias: Lightning ok; Mach-E -21.98 m (🚨); Hyundai -11.57 m (⚠️).
- Verdict: keep, ship.

## E02 — Refit coefficients with scipy on yaw_plus_cte (Rung 0)
- Rung: 0
- Hypothesis: scipy may find better coeffs than the prior cohort's published numbers.
- What I changed vs E01: ran fit-model L-BFGS-B per platform on 200-segment subsample, 80/20 route-grouped train/dev split, objective="yaw_plus_cte". Bounds wide on g, L_eff, K_us, tau, delta0.
- Result (full sim/): yaw 0.006193 rad/s (-52.1%); CTE 55.97 m (-65.8%).
  - Fit warnings: Lightning train_obj=0.054 dev_obj=0.102 (gap +87.9% ⚠️ — overfit symptom). Hyundai tau collapsed to 0.020 (vs 0.062 prior).
  - Pooled scores essentially tied with E01. CTE marginally better, yaw marginally worse.
- Verdict: revert — the marginal CTE gain isn't worth the train/dev gap warning on Lightning. E01 ships.
- Rules out: scipy fitting on this objective shape doesn't materially beat the published cohort coeffs — the rung-0 optimum is essentially flat in this neighbourhood.

## E03 — Rung-1 attempt: linear dynamic single-track on Mach-E
- Rung: 1
- Hypothesis: dynamics-formulations.md § "Rung 1" suggests slip-angle dynamic ST may capture transient regime residual (Mach-E has -22 m drift after E01, biggest CTE flag).
- What I changed vs E01: implemented the 30-line minimum-viable recipe from dynamics-formulations.md. Two-state Euler (vy, yr), forces F_yf=C_αf·α_f and F_yr=C_αr·α_r with carParams seed (m=2336, Iz=4879, l_f=1.313, l_r=1.671, C_αf=286_551, C_αr=355_912). Fit C_αf, C_αr, g, δ₀ per platform with L-BFGS-B on yaw_plus_cte.
- Result (Mach-E only): integration unstable. fit reported train_obj=inf and did_not_converge. Scoring the unfit init also produced numeric overflow in yaw RMSE.
- Verdict: revert — Euler integration of this ODE at carParams initial conditions blows up (likely the `vx · yr` coupling at the iteration scale combined with stiff C_α values). Would need RK4 + smaller substep + warm-start on vy from data, plus C_α bounding from observed peak a_lat. Costs more than the time budget allows.
- Rules out: the published rung-1 recipe is NOT plug-and-play stable at carParams priors on this dataset's sample-rate; future agents should expect to debug integrator stability before getting a fittable objective.
