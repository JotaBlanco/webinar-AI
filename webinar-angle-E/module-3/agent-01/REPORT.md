# REPORT.md — webinar-angle-E / module-3 / agent-01

## Platform & contract

- Platform: `FORD_MUSTANG_MACH_E_MK1`
- Truth channel: `yaw_rate_meas_rads` (Ford `sim.csv`)
- Operating contract: KS runs with `clamp_v_to_measured=True` and `clamp_delta_to_measured=True`. Speed and steering are inputs; the lateral residual `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` is the only metric.
- Dataset: 913,626 rows across 315 segments.
- Attribution scheme: strict marginal, fixed order V0 → V1 → V2 → V3.

## Variant ladder

| Variant | Description | RMSE overall (rad/s) | RMSE straight | RMSE steady | RMSE transient | Marginal Δ overall |
|---|---|---|---|---|---|---|
| V0 | As-shipped `yaw_rate_resid_rads` | 0.01612 | 0.00879 | 0.03169 | 0.05680 | — |
| V1 | KS recalibrated with canonical L, per-segment gyro-bias subtraction on straights | 0.01469 | 0.00496 | 0.03164 | 0.05730 | **−0.00143** (improvement) |
| V2 | Linear single-track, openpilot prior C_α (KS fallback v<2 m/s) | 0.01653 | 0.00703 | 0.03445 | 0.06235 | +0.00184 (**regression**) |
| V3 | Linear single-track, fit C_αf, C_αr bounded (5e4, 5e5) N/rad | 0.01664 | 0.00702 | 0.03478 | 0.06267 | +0.00011 (**regression**) |

Sum of marginals: −0.00051 = total drop V0→V3 (gap 0.00%, well inside the 15% tolerance).

V3 fit result: `C_αf = 1.500e5`, `C_αr = 1.500e5`, `pegged = False`. These are exactly the L-BFGS-B initial guesses — the optimizer made zero progress (silent non-convergence, not a pegged bound).

## Attribution

- **V1 owns the entire net improvement.** It cuts straight-line RMSE nearly in half (0.0088 → 0.0050) via per-segment yaw-gyro bias correction; recalibrated L is essentially neutral.
- **V2 is a regression in every regime.** Linear ST steady-state gain underestimates cornering yaw rate on this Mach-E across both steady and transient regimes.
- **V3 is V2.** The optimizer never moved off the (1.5e5, 1.5e5) prior, so the "fit" rung adds nothing.

### Per-regime contrast (sibling skill — `regime-comparison`)

Same regime column reused from the parent skill to avoid the documented mask-mismatch trap.

| Variant | Δ straight | Δ steady | Δ transient | Dominant regime |
|---|---|---|---|---|
| V0 | 0.000000 | 0.000000 | 0.000000 | — |
| V1 | **−0.00384** | −0.00005 | +0.00050 | straight |
| V2 | −0.00176 | +0.00276 | **+0.00555** | transient |
| V3 | −0.00177 | +0.00309 | **+0.00586** | transient |

Reading: V1's delta concentrates entirely on **straight** (gyro-bias correction). V2 and V3 sacrifice ~3× more in **transient** than they recover anywhere else — linear steady-state ST is the wrong model for transient cornering on this segment set.

## Regression flags

- **V2 vs V1, all three regimes.** Linear-ST steady-state gain `v·δ / (L·(1 + K_us·v²))` under-predicts yaw rate where transients and tyre nonlinearity dominate. Prior C_α from openpilot is plausibly too stiff (or too symmetric front/rear) for the Mach-E.
- **V3 vs V2, transient.** Fitting C_α inside L-BFGS-B with bounds (5e4, 5e5) terminated at the initial point: the steady-state model's loss surface is too flat near the prior for the optimizer to escape. The skill's pegged-bound regression check did not catch this failure mode — the real issue is silent non-convergence, not a bound saturation.

## Conclusion

Net improvement = V1's per-segment yaw-gyro bias correction on straights. Stepping to linear single-track loses more in cornering than it gains. To beat V1 we need a non-linear lateral model (tyre slip with saturation) or a transient-aware term — neither rung of this ladder provides one.
