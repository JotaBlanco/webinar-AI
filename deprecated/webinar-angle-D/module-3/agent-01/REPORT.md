# Lateral-Fidelity Triage — REPORT

- **Platform:** Ford Mustang Mach-E MK1 (`FORD_MUSTANG_MACH_E_MK1`), 30 of 315 available `sim.csv` segments, 86,964 rows total.
- **Truth channel:** `yaw_rate_meas_rads` is **measured truth** (decoded from the Ford party DBC IMU).
- **Operating contract:** `v` and `δ` are **clamped** to measured each step (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Lateral state (`ψ̇`, `a_y`) is free and is the scored quantity.
- **Residual under test:** `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads`.
- **Accounting scheme:** strict marginal, fixed order V0 → V1 → V2 → V3 → V4. Marginal drop = `RMSE(V_{i-1}) − RMSE(V_i)`.

## Variant ladder (yaw-rate RMSE, rad/s)

| Variant | Description | Overall | Straight | Steady | Transient | Marginal Δ vs prev |
|---|---|---|---|---|---|---|
| V0 | Baseline `yaw_rate_resid_rads` as-is | 0.01563 | 0.01044 | 0.03360 | 0.05323 | — |
| V1 | KS recalibrated (canonical `L=2.984`) + per-segment yaw-gyro bias on straights | **0.01381** | **0.00605** | 0.03477 | 0.05572 | **−0.00182 (improvement)** |
| V2 | Linear ST with prior C_α (carParams) + per-segment bias | 0.01648 | 0.00340 | 0.04559 | 0.06990 | +0.00267 (**REGRESSION**) |
| V3 | Linear ST with fit C_α + per-segment bias | 0.01659 | 0.00348 | 0.04585 | 0.07027 | +0.00010 (**REGRESSION**) |
| V4 | V3 + Ridge residual learner, LOO out-of-fold | 0.02502 | 0.00421 | 0.07143 | 0.10267 | +0.00843 (**REGRESSION**) |

## Notes (bullets only — single table rule)

- **Best variant: V1.** Sensor gate run on `out/best_variant_V1.csv` with `--baseline-rmse 0.01563`: sign-consistency PASS (corr(pred,meas)=0.995 on cornering); regression-check PASS (0.01381 ≤ 0.01563).
- **V1 wins on straights** (0.0060 vs 0.0104) — confirms the V0 baseline had a per-segment yaw-gyro DC bias that the recalibrated KS + bias subtraction removes cleanly.
- **V2 regression cause:** the linear-ST understeer-gradient correction `(1 + K_us v²)` makes cornering yaw-rate predictions smaller, but the measured-vs-KS gap on this Mach-E mix is in the **opposite** direction — V2 under-predicts cornering more than V1. The prior C_α (286 551 / 355 912 N/rad) implies more understeer than these tyres actually exhibit. Result is +27% RMSE on transient regime relative to V1.
- **V3 regression cause:** L-BFGS-B converged at the initial point `cf = cr = 150 000 N/rad` (within bounds, **not pegged** at the upper bound per v0.5 check). The loss surface is essentially flat at the start — the steady-state linear-ST functional form cannot match the measured cornering gain on this segment mix regardless of C_α inside the physical range. So V3 ≈ V2 by construction, both regressions.
- **V4 regression cause:** the Ridge residual learner is trained on V3 residuals (themselves degraded). LOO out-of-fold predictions overshoot on held-out segments because the feature set `[v, |a_y|, |δ|, sign(δ̇)]` does not generalise across the route mix; in-fold OOF RMSE on V3 residuals is 0.0130 but the *combined* `V3_pred + oof_resid` against measured is 0.0250 (the learner is correcting V3 toward measured *in-fold* but moving the wrong way OOF). Honest LOO catches it.
- **Sum-of-marginals check:** marginals sum to −0.00939; total V0→V4 = −0.00939. Within 15%? Yes (identity by definition for non-overlapping serial subtractions).
- **Most-felt absence:** a regime-stratified Cα fit. V3 fits one (C_αf, C_αr) pair globally; the Mach-E response on this sample shows the linear-ST shape is wrong on transients regardless of C_α, so a global fit is hopeless. A version of V3 that fits on the **steady** mask only — or a per-regime model selector — is the obvious next variant and is not in the v0.5 ladder.

## Shipping recommendation

- **Ship V1.** Drop the linear-ST rungs on this Mach-E segment mix until either (a) the prior is re-derived from data, or (b) the ladder grows a steady-only Cα-fit rung.

## Limitations declared

- Used 30 of 315 available Mach-E segments (deterministic first-30 in glob order). Result is directional; a full-fleet run would refine the marginals but is unlikely to reverse the V2/V3/V4 regressions given how decisively they fail across straight/steady/transient regimes simultaneously.
- Did not read sibling agents, other webinar-angle-* dirs, `_shared`, `_launch`, F1, or `raw-model`. Read only this module and the `code/`/`data/` symlinks.
