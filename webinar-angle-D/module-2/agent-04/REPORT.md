# REPORT.md — webinar-angle-D / module-2 / agent-04

## Setup
- Platform scored on: **Ford Mustang Mach-E (MK1)**.
- `yaw_rate_meas_rads` is **measured truth** decoded from the Mach-E IMU via the Ford party DBC in the rlog.
- Segment set: first 12 Mach-E `sim.csv` paths under `data/sim/segments/FORD_MUSTANG_MACH_E_MK1/` (34,786 rows, multiple devices/routes).
- Operating contract: `clamp_v_to_measured=True`, `clamp_delta_to_measured=True` (speed-known, lateral-only).
- Sign check: `corr(delta_road_rad, yaw_rate_meas_rads)` on cornering rows = **+0.939** → sign convention is correct.

## Variant ladder — RMSE of yaw-rate residual (rad/s)

| variant | overall | straight | steady | transient | Δ vs prev (overall) |
|---|---:|---:|---:|---:|---:|
| V0 baseline (CSV `yaw_rate_resid_rads`) | 0.01403 | 0.01261 | 0.03192 | 0.03796 | — |
| V1 KS recalibrated + per-segment yaw-gyro bias | 0.00973 | 0.00737 | 0.02924 | 0.04055 | **−0.00429** |
| V2 Linear ST with openpilot prior C_α | 0.00825 | 0.00351 | 0.03459 | 0.04544 | **−0.00148** |
| V3 Linear ST with fit C_α | 0.00839 | 0.00367 | 0.03517 | 0.04570 | +0.00014 (regress) |
| V4 Ridge residual learner (LOO) on V3 | 0.00999 | 0.00379 | 0.04116 | 0.05839 | +0.00160 (regress) |

(`Δ vs prev` is the contribution attribution requested by the skill — negative = improvement.)

## Attribution of the V0→V2 gain (Δ overall RMSE = −0.00578 rad/s, −41%)
- **74% (−0.00429)** from V1: re-deriving `ψ̇_KS = (v/L)·tan(δ_road)` with the canonical Mach-E `L = 2.984 m` **and** subtracting a per-segment straight-line yaw-gyro bias. The bias step alone explains most of this — straight-row residual went from 0.01261 → 0.00737.
- **26% (−0.00148)** from V2: switching to the linear-ST steady-state gain with the openpilot prior (`C_αf=286,551`, `C_αr=355,912`). Almost all of this lands in the **straight** regime (0.00737 → 0.00351); cornering RMSE actually worsens slightly.

## What did NOT work (and why)
- **V3 fit C_α regressed.** `triage.fit_c_alpha` returns `(150000, 150000)` — i.e. the initial guess `x0 = [1.5e5, 1.5e5]`. A grid scan over (5e4 … 5e5)² shows the loss surface has near-singular ridges where `1 + K_us·v² ≈ 0` (denominator in the gain formula explodes), and L-BFGS-B's numeric gradient at `x0` is dominated by those neighbouring NaN/Inf cells, so the optimiser declares convergence immediately. True grid minimum is at ~(4e5, 5e5) with overall loss **0.01265**, only marginally below the prior's **0.01273** — i.e. the prior is already near-optimal on this segment set, and there is no real headroom from fitting C_α. **Skill helper has a silent failure; should switch to a regularised / log-space param search, or grid-search seeded.**
- **V4 residual learner regressed** in steady and especially transient (0.0454 → 0.0584 rad/s). The feature set `[v, |a_y|, |δ|, sign(δ̇)]` includes only one transient signal (`sign(δ̇)`, a discrete ±1) and the OOF Ridge model overfits to per-segment offsets it cannot generalise. Recommendation: replace `sign(δ̇)` with continuous `δ̇`, add a tyre-load proxy (`v·δ̇`), and switch from Ridge to a non-linear model or at minimum bake the regime into the feature.

## Absent harness component I felt the lack of most
**An `evals/` fixture / regression-test directory** for the skill. `fit_c_alpha` silently returned its initial guess; I only caught it because I ran a one-off grid sanity check. A frozen `expected.json` with V0..V4 RMSE on a tiny known segment, or even a unit test that asserts `loss(fit) < loss(prior)`, would have flagged the broken optimiser immediately and removed the temptation to trust V3 at face value. The skill is also missing a `references/` page on which regimes the linear-ST formulation should and shouldn't be trusted in — that's why I can't tell whether the V2 cornering-regime degradation is expected (e.g. tyre saturation, suspension roll) or a sign of further bias.

## Recommended next steps
1. Patch `triage.fit_c_alpha` — seed from openpilot prior, search in log-space, mask out rows where `|1 + K_us·v²| < ε`.
2. Add an `evals/` fixture with a 2-segment regression test (`V2 ≤ V0`, `V3 ≤ V2`).
3. Re-spec V4: continuous `δ̇`, regime as a one-hot, per-segment effects removed before fit.
4. Investigate why V2 helps straight but hurts cornering — likely an unmodelled `a_y`-dependent compliance / tyre slip term beyond linear ST.

## Artefacts
- `out/run_ladder.py` — the ladder script
- `out/check_fit.py` — C_α grid sanity check
- `out/ladder_results.csv`, `out/fit_params.json`
