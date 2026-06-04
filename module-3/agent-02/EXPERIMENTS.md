# EXPERIMENTS.md

Append-only log of approaches you tried. One entry per concrete attempt. See `references/exploration-discipline.md` for the why.

Schema (every field required):

```
## E<NN> — <one-line approach name>
- Rung: 0 | 1 | 2 | 3 | orthogonal
- Hypothesis: why you thought this would help, in one line.
- What I changed vs E<NN-1>: the minimal diff.
- Result (dev): yaw <old> → <new> (Δ%); CTE <old> → <new> (Δ%).
- Verdict: keep | revert | revisit-later.
- Things this rules out: what you learned, even if the experiment failed.
```

**`Rung:` is required on every entry.** The grader's preflight checks for at least one entry tagged `Rung: 1` (or higher, or `orthogonal`). Past cohorts piled up at rung 0 — see `AGENTS.md` § "On exploration — the default is to climb". Tagging discipline:

- `Rung: 0` — kinematic single-track (V0 shape): coefficient refinements, polynomial steering scale, per-segment δ₀, lag time-constant tuning. Anything that stays in `yr_ss = v · δ / (L + K · v²)` territory.
- `Rung: 1` — linear dynamic single-track with slip angles. State variables `vy`, `yr`; lateral force `F = C_α · α`. See `references/dynamics-formulations.md` § "Rung 1" for the minimum viable recipe.
- `Rung: 2` — nonlinear tyre (Pacejka, Fiala, brush) on top of rung 1.
- `Rung: 3` — multi-body / weight-transfer coupling.
- `Rung: orthogonal` — non-physics paths (residual ML on top of a physical prior, sensor-fusion / complementary filter, etc.).

Delete this header section once you start logging, but keep the schema close to mind.

---

## E00 — V0 baseline (no changes)
- Rung: 0
- Hypothesis: establish the floor we're trying to beat.
- What I changed vs nothing: nothing — predict() passes through `yaw_rate_pred_rads`.
- Result (dev): yaw 0.01456; CTE 147.44.
- Verdict: baseline.
- Things this rules out: nothing yet.


## E01 — V1 recipe (rung-0 KS + per-segment delta0 from anti-patterns.md)
- Rung: 0
- Hypothesis: legal-cousin per-segment delta0 from input-only straight gate, platform-gated (off Lightning, on Mach-E + IONIQ-5), should close most of CTE drift.
- What I changed vs E00: implemented PLATFORM_PARAMS recipe verbatim from references/anti-patterns.md with shipped top-tier-cohort coefficients.
- Result (full sim/): yaw 0.012934 -> 0.005874 (-54.6%); CTE 163.83 -> 56.81 (-65.3%).
- Verdict: keep (forms basis for V2).
- Things this rules out: rung 0 + recipe coeffs already gets close to documented top-tier; further gains require either better coeffs or rung-up.

## E02 — V2 per-platform yaw-RMSE fit (scipy L-BFGS-B, route-grouped 80/20)
- Rung: 0
- Hypothesis: dataset-specific fit improves on the cohort-published recipe coefficients.
- What I changed vs E01: scipy.optimize.minimize on (g, L_eff, K_us, tau, delta0_or_fallback) per platform against pooled yaw RMSE on the training split; route-grouped dev held out for overfit check.
- Result (full sim/): yaw 0.005874 -> 0.005824 (-0.85%); CTE 56.81 -> 56.99 (+0.32%).
- Verdict: keep yaw (marginal); CTE slightly worse on Mach-E (cte_signed -21 m, drift not removed by yaw-RMSE fit alone).
- Things this rules out: pure yaw-RMSE fit at rung-0 with this state-space is essentially saturated within ~1% of the shipped recipe; further yaw gains will not come from rung-0 coefficient tuning.

## E03 — V3 yaw-RMSE + bias-squared penalty fit (rung-0)
- Rung: 0
- Hypothesis: adding lambda * mean_signed_residual^2 penalty steers the fit toward zero-bias and reduces CTE drift.
- What I changed vs E02: replaced pure yaw-RMSE objective with rmse^2 + 5 * bias^2.
- Result (full sim/): yaw 0.005824 -> 0.005829 (+0.09%); CTE 56.99 -> 57.27 (+0.49%); per-platform bias barely shifted.
- Verdict: revert (V2 better on both).
- Things this rules out: the residual bias on Mach-E / IONIQ-5 is not addressable by a global parameter nudge inside the rung-0 state space; it is a per-route / per-regime structure (top-CTE segments all sit on a single Mach-E route 00000000--33439c2a9c, suggesting a route-level or surface-specific effect rung 0 cannot represent).

## E04 — Rung-1 linear dynamic single-track (REQUIRED CLIMB ATTEMPT)
- Rung: 1
- Hypothesis: replacing steady-state yr_ss with the actual lateral-dynamics ODE (states vy, yr; F = C_alpha * alpha) will fit transient regime better. Default-climb attempt mandated by AGENTS.md § "On exploration".
- What I changed vs V2: implemented the minimum-viable recipe from references/dynamics-formulations.md § "Rung 1". Fixed m, Iz, a, b, C_ar from code/parameters.py (carParams). Fitted only C_af per platform on Mach-E (scalar bounded minimisation). Used 20x sub-stepped Euler integration at 1 kHz substep because 50 Hz Euler diverged (mentioned as a failure mode in the reference; confirmed empirically).
- Result (Mach-E only, full train): rung-1 yaw 0.01452 (dev 0.01157); compare V2 Mach-E yaw 0.00842 (-72% worse than V2 on Mach-E). No delta0, no steering scale g, no understeer term -- so structurally undercutting V2's calibrated rung-0.
- Verdict: revert; ship V2 (rung-0). Even with a stable integrator, raw carParams-based rung-1 with one fitted parameter does not beat a well-calibrated rung-0 model. To win it would need: (a) per-platform fit of g, delta0 in front of the dynamics layer; (b) fit C_af AND C_ar AND Iz jointly; (c) per-segment delta0 still on top. That is multi-hour work beyond the time budget.
- Things this rules out: the lazy "swap V0 for rung-1 with one fitted parameter" path is a net regression on this dataset within 45-min budget. The legitimate rung-1 win, if it exists, requires either (i) re-implementing the whole rung-0 calibration stack inside rung-1, or (ii) a hybrid that uses rung-1 only on transient regime where rung-0 lag-fit fails. Logged as evidence for the cohort.
