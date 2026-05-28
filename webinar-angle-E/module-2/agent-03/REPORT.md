# REPORT — lateral-fidelity workflow (workshop scaffold S2)

## Platform and contract

- Platform scored: **FORD_MUSTANG_MACH_E_MK1** (315 Ford Mach-E segments, 913,626 rows).
- `yaw_rate_meas_rads` is measured truth (from rlog IMU, Ford-only).
- Speed `v` and steering `δ` are **clamped** to measured under the speed-known operating contract (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). The lateral residual `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` is the only metric scored.
- Regime split (fixed thresholds): straight 785,093 rows, steady 106,978, transient 21,555.

## Variant ladder

| variant | overall | straight | steady | transient |
|---|---:|---:|---:|---:|
| V0 (baseline KS) | 0.01613 | 0.00877 | 0.03173 | 0.05680 |
| V1 (KS recalib + per-seg gyro bias) | **0.01469** | **0.00493** | 0.03168 | 0.05730 |
| V2 (Linear ST, openpilot prior Cα) | 0.01653 | 0.00701 | 0.03450 | 0.06234 |
| V3 (Linear ST, fit Cα, L-BFGS-B) | 0.01663 | 0.00700 | 0.03482 | 0.06266 |

Bold = best in column.

## Attribution

Marginal RMSE drops (positive = improvement):

- **V0→V1: −0.00144 rad/s** overall (−8.9%). Almost entirely driven by straight regime (−0.00384, −44%). Steady is flat (−0.00005), transient slightly worse (+0.00050).
- **V1→V2: +0.00184 rad/s** (regression of 12.5% vs V1). Every regime worsens. Linear ST adds slip dynamics that don't pay back on straight rows, and the prior `Cα` is not a good fit for this platform.
- **V2→V3: +0.00011 rad/s** (effectively a no-op). The Cα optimiser landed at `(1.5e5, 1.5e5)`, the midpoint of the `(5e4, 5e5)` box. `pegged=False`, but the fit clearly did not converge to anything informative — V3 ≈ V2.
- **Sum of marginals: −0.00050 rad/s.** Total V0→V3 delta: −0.00050. Match within rounding (yes, <15%).
- **Best variant is V1**, not V3. The ladder regresses past its own midpoint.

## Regressions and physical reasons

- **V1 transient**: 0.05680 → 0.05730. Per-segment straight-row gyro bias removal is estimated where the vehicle isn't yawing; subtracting that constant slightly shifts transient predictions. Marginal and expected.
- **V2 and V3 everywhere**: Linear ST adds front/rear slip with cornering stiffness `Cα`. With straight rows dominating sample count, an ST model that injects slip-driven yaw on essentially-straight motion (numerical slip ≠ 0 at low δ) raises straight RMSE; the prior Cα is also miscalibrated for the Mach-E platform.
- **V3 vs V2**: the optimiser found no useful gradient — Cα stayed at the prior. Likely the loss surface is dominated by straight rows where Cα has near-zero leverage. Flagging V3 as a non-result, not a hit-the-bound regression.

## Notes

- Workflow followed exactly as prescribed (steps 1→5, in order). No deviations. The `PARAM_BY_PLATFORM` bug warned about in AGENTS.md did not trigger for this platform — no patch applied.
- Caveat: V1's win is concentrated in the highest-count, lowest-difficulty regime (straight). The interesting regimes (steady 0.032, transient 0.057 rad/s) are essentially untouched by anything in the V1–V3 ladder. A residual learner (V4) is explicitly out of scope here; recording the gap as workshop signal.
- Caveat: `pegged=False` for V3 is technically true but misleading — Cα sat at the box midpoint. The skeleton's "regression flag" trigger (pegged at upper bound) under-fires; a "no-movement-from-prior" check would have caught this.
- Recommendation if the ladder were allowed to extend: weight the loss by regime (or fit Cα on transient+steady rows only) before declaring Linear ST a failure. As scored, V1 wins and the workflow stops there.
