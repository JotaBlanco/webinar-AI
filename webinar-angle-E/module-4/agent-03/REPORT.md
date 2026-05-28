# REPORT.md — module-4/agent-03 (RPI loop, angle-E)

## Headline
- Platform: **FORD_MUSTANG_MACH_E_MK1** (315 segments, 913 626 rows).
- Net V0→V3 RMSE change: **0.01613 → 0.01663 rad/s (−0.0005, i.e. worse).** V1 is the only variant that improves the metric; V2 and V3 regress.

## Operating contract
- Truth channel: `yaw_rate_meas_rads` (measured, present on Ford only).
- Inputs `v_mps` and `delta_road_rad` are **clamped to measured** (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Speed-state agreement is zero by construction and not the metric.
- Lateral metric: `RMSE(yaw_rate_resid_rads)` overall and per regime (`|δ| < 0.01` straight; `≥0.01 & |dδ/dt| < 0.05` steady; else transient, dt=0.02 s).

## Variant ladder

| Variant | RMSE overall | RMSE straight | RMSE steady | RMSE transient | ΔRMSE (marginal) | Attribution note |
|---|---|---|---|---|---|---|
| V0 baseline (sim.csv as-is) | 0.01613 | 0.00877 | 0.03173 | 0.05680 | — | reference |
| V1 KS recalibrated + per-segment straight-line bias | 0.01469 | 0.00493 | 0.03168 | 0.05730 | **+0.00143** | bias subtraction cuts straight RMSE 44 %; cornering unchanged |
| V2 Linear ST, openpilot prior C_α | 0.01653 | 0.00701 | 0.03450 | 0.06234 | **−0.00184** | ST gain damps yaw vs KS but the prior C_α implies more understeer than the tyre exhibits → cornering RMSE rises |
| V3 Linear ST, fitted C_α | 0.01663 | 0.00700 | 0.03482 | 0.06266 | **−0.00011** | fit returned C_αf = C_αr = 1.50e5 (= L-BFGS-B start point, **not** pegged at 5e5) — see dissent |

## Attribution accounting
- Scheme: strict marginal, fixed order V0→V1→V2→V3. `ΔRMSE_i = RMSE(V_{i-1}) − RMSE(V_i)`.
- Total V0→V3: **−0.00051**. Sum of marginals: **−0.00051**. Reconcile gap **0.0 %** (well inside 15 %).
- V1 contributes +0.00143 (yaw-gyro bias removed on straights — Phase-1's "Lightning has a non-zero mean residual" finding generalised; Mach-E also carries a small per-segment offset).
- V2 contributes **−0.00184** (regression) — biggest single change in the ladder, and the wrong direction.
- V3 contributes **−0.00011** (regression) — within numerical noise of V2.

### Regime contrast (sibling skill, deltas vs V0 RMSE; same regime mask)

| variant | Δ straight | Δ steady | Δ transient | dominant regime |
|---|---|---|---|---|
| V1 | −0.00384 | −0.00005 | +0.00050 | straight |
| V2 | −0.00176 | +0.00276 | +0.00555 | transient |
| V3 | −0.00177 | +0.00309 | +0.00586 | transient |

V1 lives entirely on straights (bias term). V2 and V3 lose all their straight-line gain back in cornering, then some — transient is where the ST prior misbehaves.

## Regression flags
- **V2 vs V1 — physical cause.** The openpilot prior C_αf=286 551 / C_αr=355 912 N/rad implies a stiff understeering linear bicycle. On these segments the simple `tan(δ)·v/L` (V1) is closer to truth in steady cornering than the gain-shaped ST. Switching to V2 imports the wrong understeer assumption.
- **V3 fit did not escape start point** — `C_αf = C_αr = 1.50e5` is exactly the L-BFGS-B initial guess in `triage.v3_linear_st_fit`. The pegged-bound check returned `pegged=False` correctly (no parameter at 5e5), but the fit is still a non-fit. Cause: the loss surface contains a singular ridge where `1 + K_us·v² = 0` (denominator flips sign at high v / low C_αr); RMSE jumps to ~10⁰–10² there, blocking the gradient. This is a skill bug surfaced by Phase 3.

## What each phase bought (RPI evidence)
- **Phase 1 (research)** surfaced two facts that drove every later decision: (a) cornering carries 6× the straight-line residual, so straight-only fixes can't help much in absolute terms, and (b) Lightning has a non-zero mean residual where Mach-E doesn't — that pushed the platform choice and pre-justified V1's bias term.
- **Phase 2 (plan)** committed to fixed marginal attribution V0→V3 *before* seeing any V2/V3 numbers. Without that lock the temptation in Phase 3 would have been to drop V2 once it regressed; instead the regression is the result.
- **Phase 3 (implement)** is where the locked plan paid off: V2 and V3 came back red, but because the ladder was fixed they're reported as honest regressions, not silently dropped.

## Plan dissent
- The locked plan said "V3 — Linear ST with fitted C_αf, C_αr". V3 as implemented in `triage.v3_linear_st_fit` does *not* actually fit on this dataset — L-BFGS-B can't cross the `1+K_us·v²=0` singular ridge from the (1.5e5, 1.5e5) start, so it returns the start point. A coarse grid run in Phase 3 (not patched into the locked plan) shows the actual loss minimum sits near (3.5e5, 3.5e5) at RMSE ≈ 0.01628, i.e. essentially indistinguishable from the prior (0.01653) and still worse than V1 (0.01469).
- Had the plan permitted, the right Phase-3 move would be either (a) replace L-BFGS-B with a global / differential-evolution search inside C_BOUNDS, or (b) constrain the search to `K_us > −1/v_max²` to keep the denominator positive. Neither would change the headline — V1 would still be the only improvement — but it would make V3 a real fit instead of a no-op.
- I did **not** rerun V3 with a global optimiser in the reported numbers, in keeping with the RPI contract that Phase 3 executes the locked plan.

## Bottom line
- The "make the lateral prediction better" answer for Mach-E is **V1 only**, with a +0.00143 rad/s overall RMSE drop (8.9 %), concentrated entirely on straights.
- V2 and V3 should not be shipped on this segment set: the openpilot ST prior is the wrong shape for these tyres, and the V3 optimiser silently fails to disagree with it.
