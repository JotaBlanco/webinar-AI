# Research

## Operating contract
- KS model in "speed-known lateral-only" mode: `v`, `δ` clamped to measured at every step. Only lateral states (ψ, ψ̇, a_y, x, y) are predicted.
- Residual convention: `pred − meas`.
- Truth available only on Ford platforms (`yaw_rate_meas_rads`, `a_lat_meas_mps2`).
- KS yaw-rate eqn (kinematic): ψ̇ = v · tan(δ_road) / L. δ_road is already produced by adapter (wheel/i_s).

## Baseline numbers (from evals/baseline_rmse.py on V0 `yaw_rate_resid_rads`)
- FORD_MUSTANG_MACH_E_MK1 (315 segments, 913626 samples):
  - overall  0.01613, straight 0.00877, steady 0.03173, transient 0.05680
- FORD_F_150_LIGHTNING_MK1 (230 segments, 667141 samples):
  - overall  0.02037, straight 0.00899, steady 0.03617, transient 0.05190

## Residual structure (first 50 Mach-E segments)
- mean resid +3.4e-4 rad/s — small bias, mostly straight-line sensor zero.
- Regression `pred = a · meas + b` → a = 0.886, b = 1.8e-4.
- That is the dominant defect: KS over-predicts yaw rate magnitude by ~13 %. Either `L` is high or `i_s` is low (δ_road too large).
- `corr(resid, δ_road) = 0.87`, `corr(resid, pred) = 0.75`. Both confirm a multiplicative (gain) defect, not random noise.
- Cornering corr(δ_road, ψ̇_meas) > 0 → ISO 8855 sign convention holds.

## Plausible failure modes
1. Steering-ratio / wheelbase scale error → multiplicative gain on ψ̇_pred (largest signal).
2. Sensor zero / bias on yaw-rate meas → additive offset (small, mostly straight).
3. No lag/transient term in KS → transient regime RMSE 3-6x straight (expected for KS).
4. `a_y_pred = v · ψ̇` coupled — must re-derive after any ψ̇ change (Rule 9).

## Variant ladder candidates
- V0: as-is.
- V1: per-platform additive bias (median resid on straight regime). Cheap, narrow.
- V2: per-platform multiplicative gain `g` (regression on cornering samples) → fixes the 0.886 thing.
- V3: V2 + V1 (gain then residual bias on straight).
- (Stretch) V4: per-segment bias on top of V3 — diagnostic, exposes calibration vs. model.

## Discipline
- Interleaved every-5th-sample train/test split.
- Same regime mask & segment set across all variants.
- `evals/schema_check.py` must pass on any derived CSV (will rebuild resid columns coupled).
