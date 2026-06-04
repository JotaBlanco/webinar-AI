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
- Result (pooled, data/sim/): yaw 0.012934 rad/s; CTE 163.83 m.
- Verdict: baseline.
- Things this rules out: nothing yet.

## E01 — V1: KS + understeer + first-order lag + platform-gated per-segment δ₀
- Rung: 0
- Hypothesis: the legal-cousin δ₀ recipe in anti-patterns.md is THE highest-leverage move on Mach-E and Hyundai (wide per-segment bias scatter), and Lightning needs a single global δ₀ (tight scatter). Coefficients copied verbatim from the top-tier shipped recipe.
- What I changed vs E00: replaced V0 passthrough with `yr_ss = v · (δ−δ₀) · g / (L_eff + K_us · v²)` + first-order lag. δ₀ per-segment for Mach-E and Hyundai via `|yr_v0|<0.03 ∧ v>5` straight gate; global δ₀ for Lightning; V0 passthrough for Tesla.
- Result (pooled, data/sim/): yaw 0.005874 (−54.6%); CTE 56.81 (−65.3%). Per platform yaw_rmse Lightning 0.00566, Mach-E 0.00859, Hyundai 0.00766.
- Verdict: keep — shipped as final-model.
- Things this rules out: nothing else needed to clear V0 floor by a wide margin.

## E02 — V2: per-platform scipy refit on yaw+CTE composite (route-grouped 200-seg subset)
- Rung: 0
- Hypothesis: V1 coefficients were copied; refitting locally with L-BFGS-B on a small route-grouped train set will push further on at least one platform.
- What I changed vs E01: L-BFGS-B over (g, L_eff, K_us, tau, δ₀) per platform on ~150–170 train segments per platform; same model shape as V1.
- Result (pooled, data/sim/): yaw 0.006238 (+6.2% vs V1, worse); CTE 58.51 (+3.0% vs V1, worse). Mach-E/Hyundai CTE drift INCREASED (Mach-E −22.3 m, Hyundai −15.8 m signed mean) where V1 had near-zero bias.
- Verdict: revert — V1 wins.
- Things this rules out: subsample-fitting on 150–200 segments per platform doesn't generalise to the full 800-segment pool; coefficient surface is flat enough that small-sample refits just chase noise. Would need full-pool fit + better objective weighting to compete.

## E03 — Rung 1: linear dynamic single-track on Mach-E, two-state Euler, one fitted param C_af
- Rung: 1
- Hypothesis: V0's first-order lag is a band-aid for missing transient dynamics. Linear DST with slip angles and a fitted C_af should better fit the transient regime where V1's residual concentrates (transient yaw RMSE 0.01647 vs straight 0.00442).
- What I changed vs E01: replaced steady-state+lag with two-state Euler integration of (vy, yr); F_yf = C_af · α_f, F_yr = C_ar · α_r with C_ar = 355,912 N/rad (carParams). Fixed m, Iz, a, b from carParams. Per-segment δ₀ reused. Single-param scalar minimisation over C_af on yaw RMSE in [150k, 500k]. Stability clamp on vy, yr.
- Result (Mach-E only, route-held-out dev): V1 dev yaw 0.00812 CTE 92.15 → Rung1 dev yaw 0.25467 CTE 118.21 (catastrophic).
- Verdict: revert — Rung 1 minimum-viable does NOT beat refined Rung 0 on this data.
- Things this rules out: Naive Euler-integrated linear DST without the first-order lag is unstable on this data — the integration overshoots during steering reversals and the optimiser cannot recover by tweaking C_af alone. To make Rung 1 competitive on Mach-E you'd need (a) RK4 or implicit integration, (b) joint fit of C_af AND C_ar (carParams prior is known to be off — anti-patterns.md), (c) keep a small first-order lag on top, (d) probably initialise vy from a few rows. The cheap "minimum viable" recipe is too cheap for this dataset. Cohort evidence: minimum-viable Rung 1 is NOT a free win.
