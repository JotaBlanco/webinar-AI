# REPORT — module-3 / agent-02 (universal agent + skill tier)

## Platform & contract

- Platform: `FORD_MUSTANG_MACH_E_MK1` (default per skill, task did not specify)
- Truth channel: `yaw_rate_meas_rads` is the measured ground truth in each Ford `sim.csv`.
- Inputs `v` and `δ` are clamped to measured (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Speed-state agreement is zero by construction and is not the metric. Only the lateral residual (RMSE of `pred − meas`) is reported.
- Segments loaded: 315 Ford Mach-E segments, 913,626 rows.
- Attribution scheme: strict marginal, fixed order V0→V1→V2→V3. Marginal drop = `RMSE(V_{i-1}) − RMSE(V_i)`. Sum of marginals reconciles to total drop within 0.0% (well under the 15% tolerance the skill mandates).

## Variant ladder (RMSE of yaw-rate residual, rad/s)

| variant | overall | straight | steady   | transient | marginal drop (overall) | notes |
|---------|---------|----------|----------|-----------|-------------------------|-------|
| V0  baseline (CSV column)         | 0.016127 | 0.008768 | 0.031733 | 0.056797 | —          | as-shipped residual |
| V1  KS recalib + per-seg bias     | 0.014693 | 0.004931 | 0.031681 | 0.057296 | **+0.001434** | improves overall and straight; tiny regression in transient |
| V2  Linear ST, prior C_α          | 0.016529 | 0.007005 | 0.034497 | 0.062343 | −0.001836  | **regression** — see flag below |
| V3  Linear ST, fit C_α            | 0.016635 | 0.007000 | 0.034822 | 0.062659 | −0.000106  | **regression** — see flag below |

Total drop V0→V3: **−0.000508 rad/s** (i.e. the ladder ends worse than it started). Sum of marginals: −0.000508. Reconciliation error: 0.0%.

V3 fit info: `C_αf = 150000`, `C_αr = 150000`, pegged = False. (The skill-prescribed L-BFGS-B start `[1.5e5, 1.5e5]` did not move — flat-gradient region. A global differential-evolution sanity check converges to `(C_αf, C_αr) ≈ (2.92e5, 2.82e5)` with overall RMSE = 0.016277 — still worse than V0/V1. The skill's V3 step under-performs the prior even when the optimizer is replaced.)

## Attribution

- **V1 is the only improvement.** Marginal drop +1.43e-3 rad/s overall. The improvement is concentrated almost entirely in the *straight* regime (RMSE drops 0.00877 → 0.00493, Δ = −3.84e-3). That is exactly what a per-segment yaw-gyro bias removal is supposed to do: it cancels constant gyro offsets that dominate straight-line residual. Cornering regimes are essentially unchanged.
- **V2 regresses everywhere except straight.** Switching from `tan(δ)` to the steady-state linear-bicycle gain inflates RMSE in steady (+2.76e-3) and transient (+5.55e-3). Cause: the linear-bicycle model assumes small-angle tyres at constant longitudinal speed; the Mach-E segments include moderate-to-large `δ_road` with non-trivial `dδ/dt`, where the linear-ST gain *under-predicts* `ψ̇`. Also V2 drops the per-segment bias that V1 had been crediting — so the straight-line improvement partially survives but is smaller than V1's.
- **V3 is a non-fit.** The L-BFGS-B optimizer the skill prescribes starts at `(1.5e5, 1.5e5)` and never leaves; the loss surface is locally flat at that point with the bounds given. Even a global DE replacement only recovers ≈0.016277 — still worse than V0. V3's marginal is essentially noise (−1e-4).

### Regime contrast (sibling skill `regime-comparison`)

| variant | Δ straight | Δ steady | Δ transient | dominant regime |
|---------|------------|----------|-------------|-----------------|
| V1 | −0.003837 | −0.000051 | +0.000500 | straight |
| V2 | −0.001762 | +0.002764 | +0.005546 | transient |
| V3 | −0.001767 | +0.003089 | +0.005863 | transient |

(Sign convention: negative = RMSE improved relative to V0; positive = regression. Same `regime` column as the parent table, so the numbers reconcile.)

## Regression flags

1. **V2 (Linear ST prior) — regression in steady & transient.** Physical cause: small-angle linearisation + steady-state assumption. Real Mach-E cornering data violates both; `tan(δ)` (V1) actually fits better than `δ/(1+K_us v²)` here.
2. **V3 (Linear ST fit) — regression vs V0 and V1.** Cause is twofold: (i) the prescribed L-BFGS-B initialisation lies in a flat region of the loss surface, so the "fit" returns its starting point; (ii) even with a global optimizer, the best Linear ST RMSE (0.01628) is still worse than V0 (0.01613) and V1 (0.01469). The functional form, not the parameters, is the limiter.

## Recommendation

Ship **V1** (KS with canonical `L` and per-segment yaw-gyro bias removal). It is the only variant that actually improves on the baseline. Skip V2/V3 on Mach-E data; if a steady-state linear model is wanted in future, fit it as a *correction* to KS rather than a replacement, and replace L-BFGS-B with a global optimizer for the C_α fit.
