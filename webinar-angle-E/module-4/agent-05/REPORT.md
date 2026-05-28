# REPORT.md — webinar-angle-E / module-4 / agent-05

## Platform
`FORD_MUSTANG_MACH_E_MK1` (315 segments, 913,626 samples at 50 Hz).

## Contract
- `yaw_rate_meas_rads` is the measured truth channel.
- `v_mps` and `delta_road_rad` are **clamped to measured**; speed-state agreement is zero by construction and is **not** the metric.
- Metric: `RMSE(yaw_rate_resid_rads)` overall and per regime (straight / steady / transient) using the skill's `triage.regime_mask`.

## Variant ladder

| variant | description | overall RMSE | straight | steady | transient | marginal Δ overall |
|---|---|---|---|---|---|---|
| V0 | baseline `yaw_rate_resid_rads` column as-is | 0.01613 | 0.00877 | 0.03173 | 0.05680 | — |
| V1 | KS recalibrated, canonical L, per-segment gyro-bias removal | **0.01469** | **0.00493** | 0.03168 | 0.05730 | +0.00143 (improve) |
| V2 | Linear ST, prior `C_αf=286551`, `C_αr=355912` N/rad, `v_min=2 m/s` KS fallback | 0.01653 | 0.00701 | 0.03450 | 0.06234 | −0.00184 (regression) |
| V3 | Linear ST, fitted `C_αf=150000`, `C_αr=150000` N/rad (bounds 5e4–5e5, not pegged) | 0.01663 | 0.00700 | 0.03482 | 0.06266 | −0.00011 (regression) |

(Per-regime numbers are RMSE in rad/s. "Marginal Δ overall" = `RMSE(V_{i-1}) − RMSE(V_i)`; positive = improvement.)

## Attribution

- **Accounting scheme:** strict marginal, fixed order V0 → V1 → V2 → V3 (telescoping). Sum of marginals = `+0.00143 − 0.00184 − 0.00011 = −0.00051 rad/s`, exactly equal to `RMSE(V0) − RMSE(V3)` (ratio 1.000, within the 15% tolerance).
- **Net effect of the ladder:** the whole ladder makes things *worse* overall (−0.00051) because V2 and V3 regress more than V1 improves.
- **Where V1 earned its delta:** entirely on the straight regime (−0.00384 rad/s). Physically this is removing the per-segment yaw-gyro DC bias — straight-line samples should have `ψ̇ ≈ 0` and the bias was ~+0.012 rad/s on the first segment alone.
- **Per-regime contrast (from `regime-comparison/compare.contrast`):**

| variant | Δ straight | Δ steady | Δ transient | dominant regime |
|---|---|---|---|---|
| V1 | −0.00384 | −0.00005 | +0.00050 | straight |
| V2 | −0.00176 | +0.00276 | +0.00555 | transient |
| V3 | −0.00177 | +0.00309 | +0.00586 | transient |

(Negative = RMSE went down vs V0 = improvement. Positive = regression.)

## Regression flags

- **V2 vs V1, steady regime:** +0.00282 rad/s. Physical cause: the Linear ST steady-state gain `v·δ / (L·(1+K_us·v²))` assumes linear tyres at small slip; the Mach-E `C_α` prior values produce a `K_us` that *under-rotates* the model relative to KS on the data's actual slip levels, so the residual sign reverses on most steady samples.
- **V2 vs V1, transient regime:** +0.00555 rad/s. Physical cause expected: Linear ST is a *steady-state* model; transients excite yaw-rate dynamics (`I_z ψ̈`) that the model can't represent. Swapping KS for Linear ST throws away KS's instantaneous geometric response without buying any transient physics back.
- **V3 vs V2:** essentially flat (−0.00011). The optimizer (`scipy.optimize.minimize`, L-BFGS-B, initial guess `(1.5e5, 1.5e5)`) returned exactly the initial point with no bound peg — flat gradient region; see Plan Dissent.
- **V1 vs V0, transient regime:** +0.00050 (mild regression). Physical cause: V1 KS prediction uses canonical L which may differ slightly from the (unknown) baseline pipeline's effective L; the bias term is calibrated on straight samples so it doesn't compensate the transient mismatch.

## Phase attribution (what each RPI phase surfaced)

- **Phase 1 (Research):** non-zero straight-line mean residual (~+0.012 rad/s) — predicted V1 would dominate before any V1 code ran. Noted Lightning's stationary stretches as a `v_min` risk; that fed the platform choice in Phase 2.
- **Phase 2 (Plan):** committed to one platform (Mach-E) and to the V0–V3 ladder, with explicit "out of scope" for V4 residual learner and Lightning. Locked the strict marginal accounting scheme and the report shape before seeing any V2/V3 numbers.
- **Phase 3 (Implement):** numerical V3-pegged-initial-guess discovered (not the upper bound — the initial point). Per RPI lock-in, the locked-plan V3 numbers stand; dissent below.

## Plan dissent

The skill's `triage.v3_linear_st_fit` uses L-BFGS-B with finite-difference gradients from initial guess `(1.5e5, 1.5e5)`. On this data the loss surface is shallow there and L-BFGS-B returns the initial guess unchanged (`fit_info = {C_αf=150000, C_αr=150000, pegged=False}`). An out-of-band Nelder-Mead probe with the same loss converged to `(C_αf, C_αr) ≈ (1.62e5, 1.42e5)` with RMSE ≈ 0.01628 — still worse than V1's 0.01469, so the *conclusion* (Linear-ST family is structurally wrong for transients on this data) is robust, but the V3 RMSE reported in the table above is **not** the true family minimum. A future run should either change the V3 optimizer in the skill or document this behaviour.

A secondary skill-body issue: `triage._load_params` does `dict["L"]`-style access, but `parameters.PARAM_BY_PLATFORM` returns a dataclass (`MachEST(L=2.984, ...)`). Patched in the driver via a `dataclasses.fields()` adapter; not modified in the skill source.
