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
- Result (dev): yaw 0.01293; CTE 163.83 (full data/sim/ pooled, 1996 segs).
- Per-platform V0: Lightning yaw 0.01633 CTE 157.5; Mach-E yaw 0.01362 CTE 148.0; IONIQ-5 yaw 0.01770 CTE 247.5; Tesla 0/0 (no truth).
- Verdict: baseline.
- Things this rules out: nothing yet.

## E01 — KS + understeer + lag, per-platform δ₀ gated (recipe from anti-patterns.md "Legal cousin")
- Rung: 0
- Hypothesis: per-segment δ₀ from input-only straight-row gate (|yr_v0|<0.03 ∧ v>5) closes the bulk of CTE drift on Mach-E and IONIQ-5; Lightning keeps a global δ₀. Top-tier m3 cohort move.
- What I changed vs E00: shipped the recipe-as-coded `predict(sim_df, platform)`: `delta_eff = (delta_road − δ₀)·g`, `yr_ss = v·δ_eff/(L_eff + K_us·v²)`, first-order lag with τ. Tesla→V0 passthrough.
- Result (dev): yaw 0.01293 → 0.005874 (-54.6%); CTE 163.83 → 56.81 (-65.3%) on the full sim tree.
- Per-platform: Lightning yaw 0.00566 CTE 62.2; Mach-E yaw 0.00859 CTE 98.7; IONIQ-5 yaw 0.00766 CTE 69.5. Mach-E and IONIQ-5 still show signed cte_drift (-22m, -12m).
- Verdict: keep — this is the shipped model.
- Things this rules out: V0 has ~half its yaw error in pure systematic δ₀ + scale, not stochastic noise.

## E02 — Nelder-Mead refit of {g, L_eff, K_us, τ, δ₀_fallback} per platform
- Rung: 0
- Hypothesis: the published recipe coefficients are slightly stale; a quick scipy refit on pooled yaw RMSE shaves more.
- What I changed vs E01: ran Nelder-Mead with sensible-range penalties for each platform's params (Lightning global δ₀, Mach-E and IONIQ-5 fallback).
- Result (dev, pooled yaw only per platform):
  - Lightning: 0.005663 → 0.005659 (-0.07%)
  - Mach-E: 0.008593 → 0.008410 (-2.1%) BUT g pegged at the 0.30 lower bound, L_eff collapsed to 0.75 → the well-documented g↔L_eff scale-invariance trap firing.
  - IONIQ-5: 0.007663 → 0.007624 (-0.5%)
- Verdict: revert. The Mach-E "improvement" is a degenerate fit (anti-patterns.md "Trusting tool-supplied bounds" → "g↔L_eff scale invariance"). The other deltas are noise. Keep E01 coefficients.
- Things this rules out: the published recipe coeffs are within ~1% of local pooled-yaw optimum on this data; further yaw-RMSE squeeze on rung-0 is dead.

## E03 — Probe alternate straight-row gates for per-segment δ₀
- Rung: 0
- Hypothesis: maybe an a_lat-proxy gate (|v·yr_v0|<0.3) or steering gate (|δ|<0.005) gives a better δ₀ estimator than the |yr_v0|<0.03 gate on Mach-E.
- What I changed vs E01: swapped the gate; everything else identical.
- Result (dev): all alternatives are worse pooled. `yr` (E01): yaw 0.00587 CTE 56.8; `alat`: 0.00622/75.3; `steer`: 0.00589/63.4; `wide_yr`: 0.00593/69.9.
- Verdict: revert to `yr` gate.
- Things this rules out: the gate choice IS the high-leverage knob, but the `|yr_v0|<0.03 ∧ v>5` flavour dominates the alternatives on this dataset.

## E04 — Rung 1: linear dynamic single-track with slip angles (Mach-E, IONIQ-5)
- Rung: 1
- Hypothesis: the residual on Mach-E/IONIQ-5 is dominated by transient dynamics that the V0 first-order lag is band-aiding; the proper two-state (vy, yr) ODE should beat it.
- What I changed vs E01: replaced `yr_ss + lag` with linear dynamic ST. State {vy, yr}, slip angles α_f, α_r, lateral forces F = C_α · α, Euler integration with 5 substeps per 50 Hz tick for stability. Fixed m, Iz, a, b, C_ar from carParams; fit g, C_αf, τ (optional output lag).
- Result (dev, 60-segment subset, pooled yaw only):
  - Mach-E: 0.008593 → 0.008502 (-1.1%); fitted g=1.25 (above plausibility), C_αf=203k pegging near upper bound. Identifiability issue (see ref doc warning).
  - IONIQ-5: 0.007663 → 0.007221 (-5.8%); fitted g=0.93 C_αf=140k τ=0.008 — looks more sane.
- Verdict: revisit-later. IONIQ-5 result is real but small (-5.8% on subset, would need full-data confirmation and CTE check). Mach-E is degenerate. Not enough time to validate CTE on integrated trajectory in this budget. Rung-1 is technically achievable but did not produce a robust win in the timebox.
- Things this rules out: under the cheap-fit recipe (fix all but C_αf and g), rung-1 is at best a single-digit % yaw improvement on this data without CTE evidence — confirming the cohort hypothesis that rung-0+δ₀ is the dominant move. The transient regime has residual structure but is a small slice of total samples.
