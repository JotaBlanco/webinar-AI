# REPORT.md — agent-03 (module-3.v3)

## Headline

| metric | V0 | V1 | shipped (V1 + GB residual) |
|---|---|---|---|
| pooled yaw RMSE (rad/s) | 0.01763 | 0.01061 | **0.00743** (-30.0% vs V1) |
| pooled CTE RMSE (m)     | 218.16  | 75.65   | **59.44** (-21.4% vs V1) |

Held-out (route-grouped 80/20 per platform): yaw 2-13% better than V1, CTE 14-51% better — the gain generalises out of route.

## What I implemented (5 candidates, 3 fully assessed, 1 shipped, 1 abandoned)

1. **residual_learner** (structure) — V1 + linear ridge head over 11 input features. R²=2-5%. Confirms residual is non-linear.
2. **lead_compensator** (structure) — V1 with steering-rate lead term `K_d·d_delta/dt` in the steady-state input. NM-refit; optimiser drove `K_d<0`, `tau→0.01` — single extra knob is not enough.
3. **residual_gb** (structure, **shipped**) — V1 + per-platform `HistGradientBoostingRegressor` over `[delta, d_delta, v, yr_v0, yr_v1, v·yr_v0, a_long]`. R²=0.27-0.74 per platform.
4. **v1_refit** (refines) — Nelder-Mead refit of V1's 6 parameters. Marginal (0.4-0.5%); confirms V1 near its parameter ceiling.
5. **dynamic_st** (structure) — linear dynamic single-track ODE with backward Euler. Abandoned: NM optimiser at full-data was too slow inside the 45-min budget on the Ioniq (84 routes / 2.3M rows). Not a structural negative result — pure budget.

## Diagnosis driving the choice

Transient regime (`|d_delta/dt|>0.05`) is 3-5% of rows but carries **30-44% of V1's yaw RMSE²** on each platform. High-`|a_lat|` is <1% of total residual — tyre saturation is **not** the issue on this dataset. Residual correlates with `delta` (-0.21 Lightning/Mach-E) and `yr_v0`, but only weakly with `d_delta` alone — pointing at a non-linear interaction the closed-form V1 cannot reach. Linear correction (E02) confirmed this. Trees were the natural next head.

## Most painful absent component

A **vectorised / parallel-segment fitting helper** (a real `fit-model` skill that doesn't iterate segment-by-segment in Python under the optimiser). My `fit_dyn_st.py` had a single-eval cost of ~0.15 s/platform on Lightning but had to call that hundreds of times under Nelder-Mead, and on the largest platform (Ioniq, ~84 routes) it did not converge inside budget. The `skills/fit-model/` slot was advertised but the actual harness shipped without a working fitter that batches segments and exposes a vectorised loss to scipy. That cost me the rung-1 dynamic-ST candidate.

Second-most-painful: no `score-model` skill — I had to roll my own scorer (~80 lines in `out/score.py`) to wire predict→sim-only→pooled metrics. Not hard, but several minutes of risk-of-bug work that should have been borrowed.

## What I almost did that the rules prevented

I almost wrote `out/REPORT.md` straight out, which the sub-agent Write filter caught. Also caught myself wanting to read `data/sim/segments/…/x_m,y_m,psi_rad` columns inside `predict()` for fast bootstrapping — would have silently broken at grading (the integrated truth leak). The strict 8-column allowlist on the sim-only mirror in `out/score.py` would have caught it but only at score-time, not at think-time.

## Single most surprising thing

The **lead-compensator optimiser drove `K_d` negative and `tau` to ~0.01** on every platform — i.e. it wants V1 to *anticipate* the steering input and *remove* the lag. This is the opposite of the AGENTS.md hypothesis that the first-order lag is a band-aid for missing transient dynamics. The fitter would rather throw the lag away and have a small anti-lead than keep V1's lag. Reading that, then seeing the GB head capture R²=0.68/0.74 on the same residual, made it concrete that the V1 lag-tau isn't approximating transient slip — it's mis-modelling a structure that's genuinely non-linear in the (delta, d_delta, v) cube.
