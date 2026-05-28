# REPORT.md — module-4 / agent-04 / webinar-angle-E

## Platform & contract
- Platform: **FORD_MUSTANG_MACH_E_MK1** (315 segments, 913,626 rows @ ~50 Hz).
- Truth: `yaw_rate_meas_rads` (measured). Inputs `v`/`δ` are clamped to measured per the operating contract. Speed-state agreement is zero by construction and is **not** the metric. The metric is `RMSE(yaw_rate_resid_rads)`.

## Variant ladder
Order is fixed V0 → V1 → V2 → V3 per the `yaw-divergence-triage` skill. Per-regime regime mask uses the **skill's `δ`-based mask** (`|δ_road| < 0.01` straight, `|δ| ≥ 0.01 & |δ̇| < 0.05` steady, else transient).

| variant | overall RMSE | straight | steady | transient | marginal vs prior |
|---|---|---|---|---|---|
| V0 — baseline KS (as-shipped) | 0.016127 | 0.008768 | 0.031733 | 0.056797 | — |
| V1 — KS, canonical `L`, per-segment straight-line bias removed | **0.014693** | **0.004931** | 0.031681 | 0.057296 | **+0.001434** |
| V2 — Linear ST, openpilot-canonical `C_αf, C_αr` (prior) | 0.016529 | 0.007005 | 0.034497 | 0.062343 | −0.001836 (regression) |
| V3 — Linear ST, `C_αf, C_αr` fit (L-BFGS-B, bounds 5e4–5e5) | 0.016635 | 0.007000 | 0.034822 | 0.062659 | −0.000106 (regression) |

- Total drop V0 → V3: **−0.00051 rad/s** (V3 is worse than V0).
- Best variant overall: **V1** (Δ vs V0 = 0.001434 rad/s, −8.9% RMSE).
- Marginal-sum accounting reconciles to 1.000× total drop (exact).

## Attribution (regime-comparison sub-table)
Signed Δ RMSE vs V0; negative = improvement.

| variant | Δ straight | Δ steady | Δ transient | dominant regime |
|---|---|---|---|---|
| V1 | **−0.003837** | −0.000051 | +0.000500 | straight |
| V2 | −0.001762 | +0.002764 | +0.005546 | transient |
| V3 | −0.001767 | +0.003089 | +0.005863 | transient |

- V1 earns its entire improvement in **straight** by removing per-segment yaw-gyro bias.
- V2 and V3 trade a small straight-line gain (they inherit some bias cancellation through the steady-state gain reshape) for **substantial** steady and transient regressions — the ST gain `1/(1 + K_us v²)` is *too soft* given the openpilot-canonical `C_α` prior on the Mach-E.

## Regression flags
- **V1 transient: +0.9%** — minor; bias subtraction nudges the transient mean. Not actionable.
- **V2 steady: +8.7%**, **V2 transient: +9.8%** — exceed the 5% threshold. Cause: openpilot ST prior on Mach-E yields `K_us > 0` (understeering); but the as-shipped baseline already absorbs much of that gain implicitly through `tan(δ)` saturation at the speeds in this dataset (most of the data is at low-to-mid v). The "softer" ST steady-state gain under-predicts yaw-rate at moderate `v·δ`.
- **V3 steady: +9.7%**, **V3 transient: +10.3%** — V3 *increased* the regression. The fit returned `C_αf = C_αr = 1.5e5 N/rad`, identical to the L-BFGS-B initial guess: the optimizer did not move (flat/noisy loss surface with finite-difference gradients over 914k rows). **Not pegged at a bound**, but effectively pinned at init.

## Phase-surfacing notes (RPI evidence)
- **Phase 1 (research)** surfaced the data-shape facts: clean residuals (no NaN), big regime-RMSE gap (transient ~6× straight on baseline), Mach-E preferable to Lightning because Lightning has a steering-offset confound. It also flagged the regime-mask choice as an open question.
- **Phase 2 (plan)** committed to Mach-E and to the skill's marginal-vs-prior accounting before any V1/V2/V3 numbers were computed. Locked the rejection of V4 residual learners, nonlinear tire fits, and Lightning.
- **Phase 3 (implement)** revealed two things the plan did not anticipate: (a) V2 *regresses* against V0 in steady and transient, and (b) the V3 fit did not move from init. Both are reported as-is, not papered over.

## Plan dissent
- The Phase-2 plan described V1 as "fit `L_eff` by least-squares on straight + steady samples". The skill helper `triage.v1_ks_recalibrated` instead uses **canonical `L`** plus per-segment **yaw-gyro bias subtraction** on straight-line samples. I followed the skill helper (because the plan also commits to the skill's marginal-vs-prior convention and the workshop's whole point is comparing identical skills under different protocols). The two recipes attack different errors — `L_eff` would have absorbed a steady-state gain error; the skill's recipe absorbs a per-segment sensor bias. Given V1's straight-RMSE collapsed from 0.00877 → 0.00493 (−44%) while steady was untouched, the skill's recipe is clearly attacking the dominant V0 error on this dataset (gyro bias, not gain) — so the deviation is defensible.
- A small parameters-API patch was required: `PARAM_BY_PLATFORM[platform]` returns a frozen dataclass instance but `triage.v1/v2/v3` indexes it like a dict (`P["L"]`). I wrapped the loader with `dataclasses.asdict` at call time; no skill code was modified.
- V3's failed fit (optimizer pinned at init) is a real implementation gap in the skill helper (L-BFGS-B with default `eps` on a 914k-row finite-difference gradient is brittle). I did **not** swap optimizers because the plan locked the helper; instead I reported it as a regression with cause, per the skill's "honest regression flags" rule.
