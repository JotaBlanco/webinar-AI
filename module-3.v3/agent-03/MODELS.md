# MODELS.md — registry of candidate models

V0 pooled (passthrough):    yaw 0.01763 rad/s, CTE 218.16 m
V1 pooled (refit ceiling):  yaw 0.01061 rad/s, CTE  75.65 m

---

## residual_learner
- dir: models/residual_learner/
- structure: differs-from-v1
- status: assessed
- pooled-yaw-rmse-dev: 0.01043
- pooled-cte-rmse-dev: 72.35
- verdict: shelved. Linear ridge head over 11 allowlist features. R²=2-5% per platform → residual is non-linear; the linear correction is under-parameterised. Motivated residual_gb.

## lead_compensator
- dir: models/lead_compensator/
- structure: differs-from-v1
- status: assessed
- pooled-yaw-rmse-dev: 0.01053
- pooled-cte-rmse-dev: 75.33
- verdict: shelved. V1 with a steering-rate lead term `K_d · d_delta/dt` injected into the steady-state input. Marginal gain (~0.8% yaw, ~0.4% CTE). Optimiser drove `K_d < 0` and `tau → 0.01`, suggesting V1's lag itself is the bigger mis-fit than the absence of a lead term — but neither knob is enough on its own.

## residual_gb
- dir: models/residual_gb/
- structure: differs-from-v1
- status: shipped
- pooled-yaw-rmse-dev: 0.00743
- pooled-cte-rmse-dev: 59.44
- verdict: SHIPPED as `final-model/`. V1 + per-platform HistGradientBoostingRegressor residual head over [delta, d_delta, v, yr_v0, yr_v1, v·yr_v0, a_long]. Pooled yaw -30%, CTE -21% vs V1. Held-out (route-grouped 80/20) confirms generalisation: dev yaw 2-13% better, dev CTE 14-51% better.

## v1_refit
- dir: models/v1_refit/
- structure: refines-v1
- status: assessed
- pooled-yaw-rmse-dev: ~0.01060
- pooled-cte-rmse-dev: ~75
- verdict: shelved. Re-fitted V1's 6 parameters per platform with Nelder-Mead. Lightning improved 0.4%, Ioniq-5 0.5%, Mach-E hit a degenerate optimum (L_eff -> 0.5). Confirms V1 is already near its parameter ceiling; structural changes are the only path past it.

## dynamic_st (abandoned)
- dir: models/dynamic_st/
- structure: differs-from-v1
- status: drafting (abandoned)
- pooled-yaw-rmse-dev: not completed
- pooled-cte-rmse-dev: not completed
- verdict: shelved within budget. Linear dynamic single-track (vy, yr) ODE with backward Euler. Per-platform fit over (g_steer, C_af, C_ar, Iz_mul) with Nelder-Mead. Single full-eval is fast (~0.15 s/platform) but the (4-parameter) NM optimiser was still too slow on the largest platform (Ioniq, ~84 routes, 2.3M rows) inside the time budget; killed after 10+ minutes with no progress reported. Identifiability concerns also flagged in `references/dynamics-formulations.md`. Not a structural negative result — just budget.
