# Phase 2 — Plan (locked)

## Platform
**FORD_MUSTANG_MACH_E_MK1**. Reasons: largest sample set (913k vs 667k), cleaner straight-line numbers in Phase 1, less stationary contamination than Lightning, and matches the SKILL's default. Lightning deferred to keep report tight.

## Variant ladder
- **V0** — baseline `yaw_rate_resid_rads` column as-is, no preprocessing.
- **V1** — KS recalibrated: `ψ̇_KS = (v/L)·tan(δ_road)` with canonical `L` from `parameters.py`, minus per-segment yaw-gyro bias measured on straight samples (`|δ|<0.01`).
- **V2** — Linear ST with prior `C_αf, C_αr`: `ψ̇_ST = v·δ/(L·(1+K_us·v²))`. Below `v_min=2 m/s` fall back to V1 KS value to avoid eigenvalue blow-up.
- **V3** — Linear ST with `C_αf, C_αr` fitted to segment set; bounded `(5e4, 5e5)` N/rad. Report fit values and pegged-bound flag.

## Attribution scheme
Strict marginal, fixed order V0 → V1 → V2 → V3. Marginal drop of V_i = `RMSE(V_{i-1}) − RMSE(V_i)`. Verify the sum of marginals is within 15% of `RMSE(V0) − RMSE(V3)`. Report any per-regime regression (negative marginal) with a physical reason.

## Reporting shape (REPORT.md sections)
1. Platform + contract statement (truth + clamps).
2. Variant ladder table — one row per variant; columns: overall RMSE, straight RMSE, steady RMSE, transient RMSE, marginal Δ.
3. Attribution — narrative + marginal sum check; sub-section embedding `regime-comparison.contrast()` per-regime signed deltas.
4. Regression flags — any variant that worsened a regime, with physical cause.
5. Phase-attribution notes — which RPI phase surfaced which decision.
6. Plan dissent (if any).

## Explicitly out of scope
- **V4 residual learner (e.g. GP/MLP on residual)** — task is to attribute physics-level improvements; learned residual would dominate but be uninterpretable.
- **Unclamping `v`/`δ`** — contract forbids it; would conflate input mismatch into the lateral metric.
- **Lightning platform** — covered by ladder design but not run; would double report length for marginal extra insight.
- **Re-derived regime mask** — reuse the skill's `triage.regime_mask` so the parent table and `regime-comparison` reconcile (SKILL "Known trap").
- **Non-linear ST / Pacejka tyres** — outside the ladder; large engineering cost.
