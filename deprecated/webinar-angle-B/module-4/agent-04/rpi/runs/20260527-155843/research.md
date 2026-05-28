# Research — 20260527-155843

## Setting

- Platform scored: **FORD_MUSTANG_MACH_E_MK1** (Mach-E). Selected per `sim-real-runtime` matrix (Ford has truth `yaw_rate_meas_rads`; Tesla does not). Mach-E preferred over F-150 because F-150 `a_lat_meas_mps2` shows `max|a_y|=1057.83` — clearly a units / outlier defect in the F-150 truth channel; would taint regime masks and scoring. Mach-E `max|a_y|=6.21 m/s²` is physical.
- Number of segments: **315**
- Number of samples: **913,626** (50 Hz, dt=0.02 s)

## Operating contract restated

- **Clamped (inputs)**: `v_mps` and `delta_road_rad` (via `clamp_v_to_measured=True` and `clamp_delta_to_measured=True`).
- **Predicted (outputs under test)**: `yaw_rate_pred_rads`, `a_y_pred_mps2`.
- **Residual under test**: `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` (pre-computed in CSV; we DO NOT regenerate sims).
- Speed-state agreement is zero by construction.

## Baseline (V0) — `yaw_rate_resid_rads` as-is

- Overall RMSE: **0.01613 rad/s**
- Per regime (regime def: straight `|δ|<0.01`; steady `|δ|≥0.01 ∧ |dδ/dt|<0.05`; transient `|δ|≥0.01 ∧ |dδ/dt|≥0.05`; dδ/dt by per-segment diff at 50 Hz):
  - Straight (n=785,093): RMSE = **0.00877**
  - Steady cornering (n=107,064): RMSE = **0.03177**
  - Transient cornering (n=21,469): RMSE = **0.05677**

## Sign-convention sanity

- `corr(delta_road_rad, yaw_rate_meas_rads)` on cornering (|δ|≥0.01): **+0.702** → sign convention OK (positive as required).

## Plausible failure modes (enumerated, not fixed)

1. **Per-segment IMU yaw-gyro bias** — `mean_yawrate_resid = -2.3e-4 rad/s` over 913 k samples is small in aggregate but per-segment bias dominates the `straight` RMSE (0.00877 ≈ a few mrad/s offset, exactly the gyro-offset signature).
2. **No tyre slip in KS** — KS gives `ψ̇ = v·tan(δ)/L`. Real vehicle exhibits understeer; predicted yaw rate is too large at high `|a_y|`. RMSE growing 6× from straight → transient is consistent.
3. **Steering ratio / road-angle conversion offset** — if `delta_road_rad` had a small offset, it would alias into straight RMSE *and* steady gain.
4. **Transient dynamics** — KS is quasi-static; in `transient` regime yaw-rate response has finite rise time (~0.1–0.3 s) that KS cannot capture. Phase lag → high RMSE.
5. **Parameter mismatch (L, i_s)** — Mach-E params are openpilot-canonical; not a likely first-order source.

## Open questions

- Are some segments stationary (v≈0)? They would inflate straight-N without informing the model.
- Is the residual sign-symmetric per regime, or does it carry a systematic bias indicating understeer in cornering?

## Wishlist

- Pre-computed `dδ/dt` and a regime label column in `sim.csv`.
- An honest LOSO CV harness already present in `tools/`.
