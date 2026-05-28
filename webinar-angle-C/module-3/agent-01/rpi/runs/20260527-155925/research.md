# Research — lateral-fidelity challenge

## Operating contract
- KS model with `clamp_v_to_measured=True`, `clamp_delta_to_measured=True`.
- Predicted lateral channel: `psi_dot_pred = (v/L) * tan(delta_road)`, `a_y_pred = v * psi_dot`.
- Residual sign: `pred - meas`. Truth only on Ford platforms.
- Sample rate ~50 Hz. Regimes from `evals/baseline_rmse.py`: straight (|δ|<0.01), steady (|dδ/dt|<0.05), transient else.

## V0 baseline (canonical, from evals/baseline_rmse.py)
- FORD_MUSTANG_MACH_E_MK1 (315 segs, 913k samples):
  - overall 0.01613, straight 0.00877, steady 0.03173, transient 0.05680 rad/s
- FORD_F_150_LIGHTNING_MK1 (230 segs, 667k samples):
  - overall 0.02037, straight 0.00899, steady 0.03617, transient 0.05190 rad/s

## Plausible failure modes (degrees of freedom worth investigating)
1. **Static yaw-rate-sensor bias** — `pred - meas` may have a non-zero median on straights where true yaw rate ≈ 0; the sensor may carry an offset.
2. **Effective steering-ratio / wheelbase miscalibration** — KS uses `L` from carParams and `delta_road = delta_wheel/i_s`. The product `tan(δ)/L` enters linearly into `ψ̇`. A per-platform multiplicative gain on δ (or equivalently on L) would absorb tyre-slip/compliance steady-state understeer that KS structurally cannot represent.
3. **Steering lag** — measured steering precedes/lags actual road-wheel motion (column compliance), inflating transient RMSE.
4. **Per-segment offsets** — yaw-rate sensor offset can drift per drive; per-segment median removal is *calibration*, not a model fix (rule 8 — must label).

## Constraints honoured
- Use `delta_road_rad` (rule 3).
- Per-platform parameter dict (rule 6).
- Interleaved every-5th split for any fit (rule 7).
- Coupled `a_y_pred = v · ψ̇_corrected` whenever ψ̇ changes (rule 9).
- Same segments + regime mask across variants (rule 11).

## Skills / tools available
- `evals/schema_check.py`, `evals/baseline_rmse.py`.
- `data/sim/segments/<PLATFORM>/.../sim.csv` already integrated.
- All variants are *post-hoc corrections on the existing CSVs*: re-running KS is out of budget; corrections applied to `yaw_rate_pred_rads` then residuals/a_y recomputed in `out/`.

## Truth statement
Yaw-rate truth = `yaw_rate_meas_rads` (Ford only). Lateral-G truth = `a_lat_meas_mps2`. No Tesla truth — Tesla excluded from scoring.
