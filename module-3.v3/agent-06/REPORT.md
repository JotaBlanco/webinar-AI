# REPORT — agent-06, module-3.v3

## Headline (dev pooled, local score against `data/sim/segments/`)

| model | yaw RMSE (rad/s) | CTE RMSE (m) | Δ yaw vs V1 | Δ CTE vs V1 |
|---|---|---|---|---|
| V1 baseline | 0.005874 | 56.81 | — | — |
| affine-v1 (refines-v1, benchmark) | 0.005859 | 54.98 | −0.3% | −3.2% |
| dynamic-st rung-1 (structure) | 0.006549 | 58.98 | +11% | +4% |
| **residual-learner (shipped, structure)** | **0.005770** | **53.78** | **−1.8%** | **−5.3%** |

Per-platform for the shipped model: Lightning 0.00557/63.4; Mach-E 0.00852/92.1 (CTE drift −22 m → **−8.9 m**); IONIQ-5 0.00750/65.5 (CTE drift −11.6 m → **+1.9 m**); Tesla 0/0 (V0 passthrough).

## Residual diagnosis (V1)

CTE on Mach-E (−22 m) and IONIQ-5 (−11.6 m) is dominated by *signed* drift, not RMS noise — V1 has a persistent gain miscalibration. `corr(V1_residual, yr_V1) = +0.34` on Mach-E, `+0.27` on `δ`, and per-platform OLS yields slopes 0.965–0.989 (i.e. V1 over-predicts yaw by 1–4%).

## What I built

- **affine-v1** (`models/affine-v1/`): per-platform `y = a·yr_V1 + b`. Pure post-correction; tagged refines-V1. Acts as a benchmark to test the gain-error hypothesis. Wins on CTE but is structurally indistinguishable from V1.
- **dynamic-st** (`models/dynamic-st/`): rung-1 linear lateral-dynamics ODE on (vy, yr) with linear tyres, RK4 sub-stepped to 2.5 ms (the references' Euler-instability warning at openpilot C_α priors at 20 ms was confirmed empirically). V1's δ₀ correction kept in front; per-platform affine post-fit applied. Loses to V1 because K_us_dyn derived from carParams Iz/C_α is lower than V1's *fitted* K_us — the dynamic-ST is under-parameterised vs the calibrated V1, exactly the cohort failure mode flagged in `dynamics-formulations.md`. Path forward (out of budget): refit C_αf, C_αr, Iz directly.
- **residual-learner** (`models/residual-learner/`, shipped): per-platform ridge linear regression on V1's residual using 7 allowlist features `[yr_V1, |yr_V1|, v, v·yr_V1, dδ/dt, δ, 1]`, λ=30 chosen by sweep. Composes additively with V1.

## Why the residual-learner wins

V1 is a fixed kinematic shape with 4 fitted scalars; it cannot express a correction that varies with `v`, `|yr|`, and `dδ/dt` independently. The residual-learner does, and the residual structure on this dataset is well-approximated by a low-rank linear combination of exactly these features. The 7-coef linear corrector beats a 6-physical-parameter rung-1 ODE because it targets V1's empirical error directly rather than redoing V1's job.

## Most painful absence in the harness

`fit-model/` was present-but-not-used. What I genuinely lacked was a **`fit-dynamic-st` skill (or even just a parameter-identifiability diagnostic)** — the rung-1 dynamic ST would probably win if C_αf, C_αr, Iz were data-fit instead of carParams-fixed, but the standard `fit-model` accepts a `predict_factory(platform, coeffs)` and asks me to choose what to fit. With ~10 minutes left I could not safely identify C_αf vs C_αr without identifiability regularisation. A diagnostic that returned "which of {C_αf, C_αr, Iz} are observable in your dev data" would have unlocked rung-1.

## Things the rules prevented me from doing

The cleanest debug for the dynamic-ST instability would have been a side-by-side visual comparison of (vy, yr) traces against truth on a high-`a_lat` segment — but the standard plotting helper goes to `_shared/` and I started reaching for a cohort-shared analysis script I knew lived outside agent-06. I caught myself and stayed inside `_shared/traj_metrics.py` plus inline numpy. The isolation rule cost ~5 minutes here.

I also noticed myself reading the `assess-candidate-model` skill body to fill in `assessment.md` per a template, when actually writing the assessment by hand was faster — almost defaulted to "run the standard battery because it's there" rather than thinking about what each model needed.

## Most surprising thing learned

The references (in particular `dynamics-formulations.md` § "rung 1") not only correctly predicted my failure mode for the dynamic-ST but also told me *why* it would fail: "rung-1 yaw RMSE worse than rung-0 ceiling because rung-0 had per-platform fit and the rung-1 attempt didn't". I read it before building, ignored it (because "I'll be different"), reproduced the failure exactly, and only then internalised it. The reference was load-bearing in a way I would normally dismiss as "obvious in hindsight" — it wasn't.
