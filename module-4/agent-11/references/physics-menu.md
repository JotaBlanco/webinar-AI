---
name: physics-menu
description: Cross-table of the physics-catalog models — for each model, the residual character it attacks, the precondition that should be visible in `residual-structure` output before picking it, and the cohort-evidence citation. Use this when `critique-residuals` says `try_residual_learner` is the wrong move and you need a *structural* climb instead.
when-to-load: After the first iterate on V1 (or rung-0 polish) shows residual structure that's not captured by current levers, AND the candidate's parent baseline is already V1.
load-cost: ~600 words.
updated: 2026-06-02
---

# physics-menu — when each catalog model is the right climb

Five physics-structurally-different models live under
[`../physics-catalog/`](../physics-catalog/README.md). Each attacks a
different residual character. This doc maps residuals → catalog models.

The reading is "if `residual-structure` says X, pick Y." If two rows could
apply, prefer the lower-rung model first (cheaper to fit, fewer params to
identify).

## The mapping

| residual signature                                                | catalog model | rung | cohort precedent              | red flag (do not pick if…) |
|---|---|---|---|---|
| autocorr lag 3–8 samples; corr with d(δ)/dt; pooled σ across folds > 5% | [`dst_lin`](../physics-catalog/dst_lin/notes.md)     | 1 | §1, §7 (every demo failed, but always with carParams) | data has no excitation — C_αf/C_αr collapse to a ratio |
| residual concentrates on outside-front in peak-lateral; \|α\| > 0.05 rad | [`dst_nl`](../physics-catalog/dst_nl/notes.md)       | 2 | §8 (V1 lag-τ mis-models a non-linear structure) | \|α\| stays < 0.04 rad everywhere → dst_nl ≈ dst_lin |
| dst_lin hurts at low \|v·ψ̇\|, helps at high                        | [`dst_regime`](../physics-catalog/dst_regime/notes.md) | 1 | §1 (rung-1 attempts hurt pooled because of low-speed) | data is high-speed only |
| dst_lin residual is autocorrelated at lag 1–3 (very short), not feature-correlated | [`dst_relax`](../physics-catalog/dst_relax/notes.md)  | 2 | §8 (specifically the v-dependent transient) | low-speed data: τ_relax = σ/v too large |
| residual concentrates in brake-into-corner segments; Lightning specifically | [`dst_load`](../physics-catalog/dst_load/notes.md)    | 3 | §2, §9 (Lightning lagging at +21% vs +55% on others) | data has near-zero a_long throughout |
| residual scales with a_lat² in fast curvature; Lightning especially; per-axle stiffness asymmetry visible | [`dst_twin_track`](../physics-catalog/dst_twin_track/notes.md) | 2 | §2 + §9 (alt mechanism for Lightning gap — lateral vs longitudinal load transfer) | low-curvature data; a_lat small everywhere |
| residual scales with `a_long_mps2 · delta_road_rad` (combined-slip diagnostic) | [`dst_combined_slip`](../physics-catalog/dst_combined_slip/notes.md) | 2 | §8 alt — the friction-circle interpretation of the V1 lag mis-model | highway cruising; \|a_long\| ≈ 0 everywhere |
| residual scales with \|δ\| at steady-state (not d(δ)/dt) — a steady-state nonlinearity | [`dst_steer_compliance`](../physics-catalog/dst_steer_compliance/notes.md) | 2 | §8 alt — V1 lag mis-modelling compliance, not tyre dynamics | uniform steering amplitude (k_ackermann unidentifiable) |

## How to combine

The eight catalog models are NOT mutually exclusive. The intended
composition order (rung-1 → rung-2 → rung-3):

1. Start at V1 (rung 0).
2. Add **dst_lin** if §1's autocorrelation signature appears → rung 1.
3. From dst_lin, branch to one of the rung-2 models depending on residual
   character:
   - **dst_nl** if residual concentrates at high α (lateral saturation),
   - **dst_relax** if residual is short-lag-autocorrelated (carcass dynamics),
   - **dst_combined_slip** if residual scales with `a_long · δ`
     (longitudinal × lateral friction-circle coupling),
   - **dst_steer_compliance** if residual scales with steady-state |δ|
     (compliance, not transient),
   - **dst_twin_track** if residual scales with a_lat² in fast curvature
     (lateral load transfer),
   - **dst_regime** if dst_lin works at high speed but breaks at low speed
     (a meta-strategy that composes onto dst_lin, listed in the rung-1 row
     because it changes the *gating* of the rung-1 model, not the model
     itself).
4. From any rung-2, branch to **dst_load** if the residual on Lightning
   specifically refuses to close (longitudinal load transfer — the third
   rung, coupled long/lat dynamics).

The `launch-rungs/manifest.yaml` wires 5 of the 6 subagent slots to one
catalog model each (the 6th runs the orthogonal residual-learner head
that lives outside the physics catalog). The three newer models
(dst_twin_track, dst_combined_slip, dst_steer_compliance) are not bound
to a manifest slot by default — they're available for a 2nd-round
fan-out on the leading branch's neighbourhood (which the orchestrator's
90-min budget was sized to allow). The agent can either retarget a
launch-rungs slot or copy them in manually mid-run.

## What this menu deliberately doesn't include

The eight catalog models cover state-space dynamics + tyre force +
load transfer + steering compliance. Things deliberately not in the
catalog (with reasons):

- **Neural / GB residual head.** Cohort §4 evidence says +1–5% CTE
  reliable; this is the `try_residual_learner` route in
  `critique-residuals`, not a physics structure. Orthogonal to the
  physics catalog — can be stacked on top of any catalog model.
  Sketched as `dst_v1_plus_gb_residual` in
  [`build-your-own-model.md`](build-your-own-model.md) if you want a
  physics × ML composition.
- **MPC integration / model-predictive-control trajectory.** Out of
  scope for the operating contract (predict() is one-pass per sample,
  not a closed-loop optimisation).
- **State estimator / particle filter.** Same scope reason.
- **Roll-rate dynamics.** Sketched as `dst_roll` in
  [`build-your-own-model.md`](build-your-own-model.md). Adds a third
  state φ̇ + camber-thrust coupling. Not in the catalog because the
  m4 cohort hasn't yet shown a residual that demands it; dst_twin_track
  captures the steady-state lateral load transfer that roll dynamics
  would have produced more accurately in the transient.

## Build a 9th when the 8 don't fit

The catalog is a seed, not a search space. When the residual you're
seeing doesn't match any of the rows above:

1. Identify which of the four structural dimensions (state, tyre,
   coupling, regime — see [`build-your-own-model.md`](build-your-own-model.md))
   your new model would change.
2. Copy the nearest catalog model into `physics-catalog/<new_name>/`.
3. Edit `predict.py` and `fit.py` to reflect the change.
4. Run `python -m physics-catalog._audit` — must be 100% green.
5. Add a row to the table above + this doc.

The eight sketches at the bottom of `build-your-own-model.md`
(`dst_roll`, `dst_aero`, `dst_pacejka_full`, `dst_brush`,
`dst_steer_rate`, `dst_implicit_euler`, `dst_v1_plus_gb_residual`,
`dst_per_platform_ridge_intercept`) are the next-most-likely
candidates — pick from there if your residual doesn't suggest something
even more specific.

## Cohort-evidence cross-reference

- `references/m4-cohort-findings.md` §1 (rung-1 attempts, fit-C_α failure)
- `references/m4-cohort-findings.md` §2 (Lightning vs Mach-E/IONIQ
  per-platform gap)
- `references/m4-cohort-findings.md` §4 (residual-learner orthogonal — NOT
  in this menu, lives in critique-residuals as the parallel route)
- `references/m4-cohort-findings.md` §6 (route-grouped CV; bias-without-
  route-CV gate — every catalog `fit.py` writes route_cv_sigma)
- `references/m4-cohort-findings.md` §7 (under-parameterisation of rung-1)
- `references/m4-cohort-findings.md` §8 (V1 lag-τ mis-models a non-linear
  structure — motivates dst_nl and dst_relax separately)
- `references/m4-cohort-findings.md` §9 (m4.v1 cohort stragglers, gates
  added in v1.01 — orthogonal to this menu but enforced on every catalog
  use too)
