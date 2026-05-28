# Phase 1 — Research

## Platforms available
- `FORD_MUSTANG_MACH_E_MK1` — 315 sim.csv files, 913 626 rows. Has `yaw_rate_meas_rads` (truth).
- `FORD_F_150_LIGHTNING_MK1` — 230 sim.csv files, 667 141 rows. Has truth.
- `TESLA_MODEL_3` — present in tree but per skill metadata has no `yaw_rate_meas_rads`. Out.

## Sample sizes per regime (mask: |δ_road|<0.01 straight; ≥0.01 & |dδ/dt|<0.05 steady; else transient, dt=0.02 s)
- Mach-E: straight 785 093 / steady 107 020 / transient 21 513 (86 / 12 / 2 %).
- Lightning: straight 520 946 / steady 114 652 / transient 31 543 (78 / 17 / 5 %).

## Baseline residual (column as-is, no preprocessing)
- Mach-E RMSE overall **0.01613 rad/s**; straight 0.00877, steady 0.03177, transient 0.05672.
- Lightning RMSE overall **0.02037 rad/s**; straight 0.00899, steady 0.03614, transient 0.05191.
- Both: residual concentrated in cornering, ~6× the straight value on transients. Cornering is the smart-zone.

## Anomalies
- Lightning has a non-zero residual mean (-0.00363 rad/s vs Mach-E -0.00023). Suggests a yaw-gyro bias / stationary offset that V1's straight-line bias subtraction should mop up.
- Both platforms have meaningful low-v populations (Mach-E 11.3 %, Lightning 16.9 % of samples below 2 m/s). V2's ST gain diverges at v→0, so the v_min=2 fallback is load-bearing — especially for Lightning.
- No NaN runs in `yaw_rate_resid_rads`. `yaw_rate_meas` peak ≈ 0.9 rad/s on both, plausible.
- delta_road_rad first-difference can spike — derivative-based regime mask could mis-classify single noisy samples as transient; small effect at our sample sizes.

## Open questions before locking the ladder
- Mach-E or Lightning? Mach-E has the cleaner mean residual and bigger sample. Lightning has worse RMSE and a bigger low-v share, so the ST fallback story is louder there — but it's also a noisier platform to demo a clean ladder on.
- Should V3 fit per-segment or pooled? Skill says fit to the segment set → pooled.
- Do we run regime-comparison? Optional. Worth doing because the transient regime is where the lift will land and it gives us a real attribution sub-table.
