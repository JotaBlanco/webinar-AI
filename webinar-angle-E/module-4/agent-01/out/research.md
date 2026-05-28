# Phase 1 — Research (raw data look)

## Platforms available
- `FORD_MUSTANG_MACH_E_MK1` — 315 sim.csv, N=913,626 rows. Has `yaw_rate_meas_rads` (measured truth).
- `FORD_F_150_LIGHTNING_MK1` — 230 sim.csv, N=667,141 rows. Has `yaw_rate_meas_rads`.
- `TESLA_MODEL_3` — 1025 sim.csv, N huge, but **no `yaw_rate_meas_rads` column**. Out of scope for lateral-fidelity (no truth channel).

## Baseline residual stats (column `yaw_rate_resid_rads`, no preprocessing)

Mach-E
- overall RMSE = 0.01613 rad/s, mean = -0.00023, std = 0.01613
- per regime: straight 0.00877 | steady 0.03173 | transient 0.05680
- regime counts: straight 785,093 (86%) | steady 106,978 (12%) | transient 21,555 (2%)
- low-v share (v<2 m/s) = 11.3%
- NaN% = 0.0

Lightning
- overall RMSE = 0.02037 rad/s, mean = -0.00363 (≈ persistent bias), std = 0.02004
- per regime: straight 0.00899 | steady 0.03617 | transient 0.05190
- regime counts: straight 520,946 (78%) | steady 114,839 (17%) | transient 31,356 (5%)
- low-v share (v<2 m/s) = 16.9% (skill flagged this)
- NaN% = 0.0

## Anomalies / observations
- Lightning baseline residual has a clear non-zero mean (-3.6e-3) — straight-line yaw-gyro bias is real and segment-specific. Mach-E mean is near zero in aggregate but may still be per-segment.
- Transient-cornering RMSE is ~6× steady on Mach-E, ~5.7× on Lightning. The headline number is dominated by straights (sample share) but the *error* is concentrated in transients.
- Lightning v<2 m/s share is 17% → V2 low-v fallback to KS will matter; otherwise ST eigenvalues blow up.
- Both platforms: no NaN runs; sign convention appears consistent (mean meas yaw rate small but non-zero).

## Open questions
- Is per-segment yaw bias large enough that V1 alone closes most of the straight-regime gap?
- Does V2 (prior C_α) regress on transients vs. V1 (likely — prior is generic)?
- Will V3's fit peg at the upper bound (5e5 N/rad) for stiff EV tyres? Mass is high on Lightning.
- Should we run the sibling regime-comparison skill to attribute per-regime?

## Phase 1 skill metadata read
- yaw-divergence-triage: V0→V1→V2→V3 ladder, marginal-RMSE attribution, default platform Mach-E.
- regime-comparison: optional per-regime contrast diagnostic.
