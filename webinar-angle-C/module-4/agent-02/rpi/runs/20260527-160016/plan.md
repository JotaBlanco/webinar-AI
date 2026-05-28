# Plan — variant ladder (locked)

Platform: **FORD_MUSTANG_MACH_E_MK1**. Single segment set, all 315 segments.
Regime mask: identical to `baseline-residual` (δ<0.01 straight; δ≥0.01 & |δ̇|<0.05 steady; else transient).
Split: interleaved, every 5th sample → test, remaining → train (per `ablation-study`).
Attribution: marginal Δ = RMSE(V_{i-1}) − RMSE(V_i) on the held-out test set.

## Ladder (additive, monotone, fixed order)

### V0 — residual as-shipped
Pure `yaw_rate_resid_rads`. Reference comes from `baseline-residual`.

### V1 — per-platform yaw-rate bias removal
Fit a single scalar `b = median(ψ̇_pred − ψ̇_meas)` on the **train** half (interleaved). Apply `ψ̇_pred' = ψ̇_pred − b` to test.
- Physical hypothesis: a small fixed IMU mounting / zero-rate offset shows as a constant median residual.
- Direction: drop in the straight RMSE primarily.
- Falsifier: if straight RMSE doesn't drop, the residual has no DC component to remove.
- Label: **per-platform**, one scalar.

### V2 — steering lag alignment
Fit a single integer lag `k ∈ [-10, +10]` samples (50 Hz → ±200 ms) that minimises train RMSE after shifting `δ_road` by `k` and recomputing `ψ̇_pred = v · tan(δ_shifted) / L`. Then re-apply V1 bias on the shifted predictions.
- Physical hypothesis: δ reported on CAN lags the actual road-wheel angle felt by the IMU.
- Direction: large drop in transient, small or none in straight/steady.
- Falsifier: if best k=0, no lag exists.
- Label: **per-platform**, one integer.

### V3 — effective wheelbase fit
Fit a single scalar `L_eff` minimising train RMSE on `ψ̇_pred = v · tan(δ_shifted) / L_eff` with V1 bias still applied. Bound `L_eff ∈ [0.5L, 1.5L]` to keep physical.
- Physical hypothesis: effective wheelbase under compliance/scrub differs from carParams `L`.
- Direction: drop in steady regime (gain error).
- Falsifier: if L_eff comes out within 1% of canonical L, the parameter wasn't the issue.
- Label: **per-platform**, one scalar.

## Stop rule
Three additive variants. Attribution-coherence < 0.15 required.
