# Phase 1 — Research

## Platforms and truth
- `FORD_MUSTANG_MACH_E_MK1` — 315 sim.csv segments, has `yaw_rate_meas_rads` (measured truth).
- `FORD_F_150_LIGHTNING_MK1` — 230 sim.csv segments, has truth.
- `TESLA_MODEL_3` — 1025 segments, **no truth column** — cannot do lateral fidelity.

## Sample sizes
- Mach-E: 913,626 rows total. Straight 785,093 / steady 128,515 / transient **18**.
- Lightning: 667,141 rows total. Straight 520,946 / steady 146,173 / transient **22**.

## Baseline residual RMSE (yaw_rate_resid_rads, as-is, no preproc)
- Mach-E overall: **0.01613 rad/s**. straight 0.00877 / steady 0.03714 / transient 0.02941.
- Lightning overall: **0.02037 rad/s**. straight 0.00899 / steady 0.04006 / transient 0.07349.

## Anomalies
- "Transient cornering" buckets are absurdly small (18 and 22 rows) — the regime mask threshold (|dδ/dt|≥0.05 rad/s) is rarely met because steering is sampled smoothly. Any transient-regime stat is essentially noise; do not over-interpret.
- Straight residual is ~5x smaller than steady — strong evidence the cornering gain is mis-set, not a gyro bias dominating.
- Lightning steady residual (0.040) and overall (0.020) are both ~25% worse than Mach-E — heavier truck, prior C_α likely poorer fit.
- NaNs: 0% in residual column on either platform. Clean.
- Lightning has stationary stretches per the SKILL note — `v_min` fallback will matter for V2/V3.

## Open questions before picking a ladder
1. Which platform — Mach-E (default, cleaner) or Lightning (worse residual, more headroom)? SKILL defaults to Mach-E unless stated. Task is silent → Mach-E.
2. Will V3's fitted C_α peg at the upper 5e5 bound on Mach-E? If so V3 may regress vs V2 and we must flag.
3. Is per-segment gyro bias on straight samples actually nonzero, or already centered? V1's contribution hinges on this.
4. Marginal-RMSE attribution sums to ≤15% of total drop? — verify in Phase 3.
