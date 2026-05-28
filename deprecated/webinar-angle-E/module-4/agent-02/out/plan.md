# Phase 2 — Plan (locked)

## Platform
`FORD_MUSTANG_MACH_E_MK1` — SKILL default; cleaner data; 315 segments; truth present; Lightning's tiny transient bucket and stationary stretches add noise without buying signal for a 15-min run.

## Variant ladder (fixed order, V0 → V3)
- **V0** — baseline: `yaw_rate_resid_rads` from sim.csv as-is. No preprocessing.
- **V1** — KS recalibrated: recompute ψ̇_KS = (v/L)·tan(δ_road) with canonical L from `parameters.py`; subtract per-segment gyro bias estimated on straight samples (|δ|<0.01).
- **V2** — Linear ST with prior C_α from `parameters.py`, K_us formula; KS fallback below v_min = 2 m/s.
- **V3** — Linear ST with C_α fitted to the segment set, bounded (5e4, 5e5) N/rad; flag pegged bounds.

## Attribution
Strict marginal, fixed order. Per-variant drop = RMSE(V_{i-1}) − RMSE(V_i). Compute overall and per-regime. Marginal drops must sum to within 15% of total drop (V0 − V3); state and verify in report.

## Reporting shape (REPORT.md sections)
- Platform + contract statement (v, δ clamped; truth = yaw_rate_meas_rads).
- Variant ladder table: rows V0..V3, columns overall RMSE, straight, steady, transient, marginal drop, attribution %.
- Regression flags (per-regime worsening with physical reason).
- Phase-attribution callout: which phase surfaced which decision.
- Plan dissent (only if mid-Phase-3 finding conflicts with this plan).

## Explicitly out of scope
- V4 residual learner (data-driven correction) — overfits 315 segments; not in skill ladder.
- Unclamping v or δ — violates operating contract.
- Lightning platform — secondary; out of scope for this run.
- Dynamic ST / tire saturation models — beyond skill ladder, would break attribution accounting.
- regime-comparison sibling skill — optional in SKILL; skip to keep run tight.
