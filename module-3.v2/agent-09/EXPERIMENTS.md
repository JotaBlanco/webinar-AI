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
- Result (pooled, all platforms, data/sim/): yaw 0.012934 rad/s; CTE 163.83 m.
- Verdict: baseline.
- Things this rules out: nothing yet.

## E01 — Anti-patterns recipe (rung-0 + per-seg δ₀, cohort-default coeffs)
- Rung: 0
- Hypothesis: apply the documented top-tier recipe verbatim (KS + understeer + lag + platform-gated per-segment δ₀; Lightning global δ₀; Mach-E/IONIQ-5 per-segment; Tesla V0 passthrough).
- What I changed vs E00: implemented `final-model/predict.py` from `references/anti-patterns.md` § "The legal cousin". Coefficients = cohort published numbers.
- Result (pooled): yaw 0.012934 → 0.005874 (−54.6%); CTE 163.83 → 56.81 (−65.3%).
- Verdict: keep as baseline for further fitting.
- Things this rules out: nothing — confirms the recipe holds up.

## E02 — Per-platform Powell refit of {g, L_eff, K_us, τ, δ₀}
- Rung: 0
- Hypothesis: cohort coefficients are a prior; refit per-platform via Powell against pooled yaw RMSE (v > 2 mps mask). Constrain Mach-E `L_eff ∈ [2.5, 3.5]` to break the g↔L_eff scale invariance the anti-patterns doc warned about (an unconstrained Nelder-Mead pass collapsed to L_eff=1.56, g=0.63 — visibly the wrong minimum even though RMSE was similar).
- What I changed vs E01: coefficients refit via scipy.optimize.minimize (Powell). Constrained Mach-E L_eff prior. Coeffs in `final-model/coeffs.json`.
- Result (pooled): yaw 0.005874 → 0.005820 (−0.9%); CTE 56.81 → 57.04 (+0.4%). Per-platform: Lightning yaw 0.00566→0.00566; Mach-E 0.00859→0.00840; IONIQ-5 0.00766→0.00762.
- Verdict: keep — small but principled. Mach-E CTE-drift signed bias remains at −21 m which yaw-RMSE refit cannot fix; that's a shape misfit, not a bias offset.
- Things this rules out: pooled yaw-RMSE objective alone cannot close the Mach-E CTE drift. A CTE-aware fit or a higher rung would be needed.

## E03 — Rung-1 minimum viable attempt (Mach-E only, dev split)
- Rung: 1
- Hypothesis: documented in `references/dynamics-formulations.md` § "Rung 1" — replace the steady-state-with-lag scaffold with a linear dynamic single-track ODE (states vy, yr; lateral force F = C_α·α). Fix m, Iz, l_f, l_r, C_αr from `code/parameters.py` (MachEST openpilot priors); fit only C_αf per platform via `scipy.minimize_scalar` on pooled yaw RMSE.
- What I changed vs E02: implemented `out/rung1_attempt.py`. 4× sub-step Euler integration, vx clamped > 1 m/s, stability guard on |yr|>5. Route-grouped 80/20 train/dev split over the first 60 Mach-E segments. Compared against the shipped rung-0 predict on the same dev split.
- Result (Mach-E, dev): rung-0 yaw 0.005764 → rung-1 yaw 0.005625 (−2.4%, Δ = −0.139 mrad/s). Best-fit C_αf = 352,681 N/rad (~1.23× the openpilot prior of 286,551; well inside `(40k, 400k)`).
- Verdict: revisit-later. Genuinely marginal win on Mach-E dev, but (a) single platform, (b) yaw-only — CTE not measured; (c) no τ-lag layer, so high-frequency response not equivalent; (d) the −0.14 mrad/s gap is within run-to-run noise. Not worth shipping over rung-0 given time budget and the platform-generalisation risk.
- Things this rules out: rung-1 does NOT obviously dominate rung-0 on this dataset for Mach-E. The cohort's hypothesis ("nobody knows if rung-1 pays here") is now slightly evidenced as "maybe, but the rung-0 ceiling is close enough that the lift is marginal".
