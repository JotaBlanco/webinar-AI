# Phase 2 — Plan (locked)

## Chosen platform
`FORD_MUSTANG_MACH_E_MK1`. Reasons: (a) skill default; (b) larger N (914k vs 667k); (c) lower low-v share (11% vs 17%) so V2 ST is on more stable ground; (d) Lightning's strong segment bias is a confound that V1 already targets — Mach-E gives a cleaner ladder.

## Variant ladder
- **V0** — baseline `yaw_rate_resid_rads` column, no preprocessing. RMSE overall + per regime.
- **V1** — KS recalibrated: ψ̇ = (v/L)·tan(δ_road) with canonical L; subtract per-segment yaw-gyro bias estimated on straights (|δ|<0.01). Helper `triage.v1_ks_recalibrated`.
- **V2** — Linear single-track with **prior** C_αf, C_αr from `parameters.py`; low-v fallback to KS below v=2 m/s. Helper `triage.v2_linear_st_prior`.
- **V3** — Linear ST with **fitted** C_αf, C_αr (L-BFGS-B, bounds 5e4–5e5 N/rad). Helper `triage.v3_linear_st_fit`. Flag pegging.

## Attribution scheme
Strict marginal, fixed order V0→V1→V2→V3. Marginal drop_i = RMSE(V_{i-1}) − RMSE(V_i). Sum-check: marginals must sum within 15% of (RMSE_V0 − RMSE_V3). State scheme in REPORT.

## Reporting shape (REPORT.md section headers)
1. Platform & contract statement
2. Variant ladder table (cols: variant | overall | straight | steady | transient | marginal Δ | notes)
3. Attribution (marginal accounting + 15% check; optional per-regime sub-table via `regime-comparison`)
4. Regression flags (per-regime regressions with physical cause)
5. RPI provenance (which phase surfaced which decision)
6. Plan dissent (only if mid-Phase-3 reason emerged)

## Out of scope (considered, rejected)
- **V4 residual learner / GP / NN** — out of skill scope, no held-out split defined, attribution becomes opaque.
- **Nonlinear single-track w/ Pacejka** — needs slip-angle tyre data we do not have.
- **Tesla platform** — no `yaw_rate_meas_rads` truth channel.
- **Lightning platform** — secondary; can re-run if Mach-E gives a pegged or degenerate fit.
- **Per-segment fit of C_α (V3-by-source)** — overfits; the skill specifies a single global fit.
- **Unclamping v or δ** — contract violation; speed-state agreement is zero by construction.
