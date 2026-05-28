# Research — 20260527T140005Z

## Setting

- Platform scored: **FORD_MUSTANG_MACH_E_MK1** (primary). Spot-check on FORD_F_150_LIGHTNING_MK1.
- Number of segments: 315 (Mach-E), 230 (F-150).
- Number of samples: 913,626 (Mach-E), 667,141 (F-150).

## Operating contract restated

- Clamped (inputs): `v_mps` and `delta_road_rad` (via `clamp_v_to_measured=True`, `clamp_delta_to_measured=True`).
- Predicted (outputs under test): lateral states — `yaw_rate_pred_rads`, `a_y_pred_mps2`, plus positions/heading.
- Residual under test: `yaw_rate_resid_rads = yaw_rate_pred_rads - yaw_rate_meas_rads` (rule 1, `pred - meas`).

## Baseline (V0) — no preprocessing

- Overall RMSE on `yaw_rate_resid_rads` (Mach-E): **0.01613 rad/s**.
- Per regime (regime mask from `evals/baseline_rmse.py`: |δ|<0.01 → straight; |δ|≥0.01 & |dδ/dt|<0.05 → steady; else transient):
  - Straight: 0.00877
  - Steady cornering: 0.03173
  - Transient cornering: 0.05680
- F-150 (sanity): overall 0.02037; straight 0.00899; steady 0.03617; transient 0.05190.

The error is dominated by **transient cornering** (×6 of straight) and **steady cornering** (×3 of straight). Straight-line residual is near sensor floor.

## Sign-convention sanity

- `corr(delta_road_rad, yaw_rate_meas_rads)` on cornering samples expected positive (left-positive ISO 8855). To be verified by `evals/schema_check.py` on the variant CSV.

## Plausible failure modes (enumerate, do not fix yet)

- **Static yaw-rate gain mis-scaled**: KS predicts `ψ̇ = v · tan(δ)/L`. If the road-wheel angle is off by a constant scale (steer-ratio mis-cal post-clamp), steady-state ψ̇ is biased proportional to δ. Would show as a per-platform gain on the residual vs δ_road.
- **Constant bias on δ_road or on the truth yaw-rate sensor**: a small offset shows up as nonzero residual on straights but is even larger on cornering because KS pred is sensitive there.
- **Phase / latency between commanded δ and measured ψ̇**: KS is instantaneous; real vehicles have tire lag + sensor latency (~50–150 ms). Would dominate the **transient** regime specifically.
- **Missing dynamic terms (understeer)**: KS has no `m`, `I_z`, `C_α`. Real vehicle at speed under-steers, so KS over-predicts ψ̇ on steady cornering. Would show ψ̇_pred/ψ̇_meas > 1 at high `v·δ`.
- **Per-segment sensor offsets**: yaw-rate sensors drift per power-cycle. A per-segment median bias correction would help but is calibration, not model improvement (rule 8).

## Open questions

- Does the residual scale with `v · δ_road` (gain issue) or with `dδ/dt` (latency)?
- Are there per-segment yaw-rate offsets large enough to mask the model error?

## What I would want next (wishlist)

- A `tools/` script that loads all sim CSVs once with interleaved-5 train/test split, fits gain/bias/lag as separate degrees of freedom, and reports marginal RMSE drop per regime.
