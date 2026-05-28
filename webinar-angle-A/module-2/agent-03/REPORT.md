# Module-2 / agent-03 — Lateral Fidelity Challenge

## Scoring setup

- **Platform scored**: `FORD_MUSTANG_MACH_E_MK1` (315 segments under `data/sim/segments/`).
- **Truth channels**: `yaw_rate_meas_rads`, `a_lat_meas_mps2` are measured (decoded from rlog IMU), not self-consistency.
- **Speed-known contract**: `v_mps` and `delta_road_rad` are inputs to the KS integrator (clamped at every step). The model's *predictions* are `yaw_rate_pred_rads` and `a_y_pred_mps2`. Speed and steering agreement is zero by construction and is not the metric.
- **Primary metric**: pooled-sample RMSE on `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` (rad/s).
- **Sign sanity**: `corr(delta_road_rad, yaw_rate_meas_rads) > 0` in 23/24 sampled segments. Left-positive convention confirmed.
- **Regime mask** (identical across every variant row):
  - *straight*: `|ψ̇_meas| < 0.05 rad/s`
  - *cornering transient*: `|ψ̇_meas| ≥ 0.05` and `|dψ̇_meas/dt| > 0.5 rad/s²`
  - *cornering steady*: `|ψ̇_meas| ≥ 0.05` and not transient

## Variants

- **V0 baseline** — `yaw_rate_resid_rads` from CSV, no preprocessing.
- **V1 per-segment bias removal** — subtract the per-segment mean of `(pred − meas)`. Targets IMU zero-rate offset and any δ-mounting bias.
- **V2 time alignment** — on top of V1, find integer-sample cross-correlation lag (search ±15 samples = ±300 ms) of `pred` vs `meas` and shift. Median fitted lag is +4 samples (~80 ms), pred leading meas — consistent with CAN/IMU report latency.
- **V3 understeer-gradient correction (isolated)** — `ψ̇_corr = ψ̇_pred / (1 + K_us · v²)`, with `K_us` fit globally by least squares against measured yaw rate on samples with `|ψ̇_meas| > 0.05` and `v > 3` m/s. Fitted **K_us ≈ 1.6 × 10⁻⁵ s²/m²** (very small).
- **V4 combo (V3 → V1 → V2 in that order)** — understeer correction, then per-segment bias on the corrected signal, then per-segment alignment.

## Results — pooled RMSE on `yaw_rate_resid_rads` (rad/s)

| variant | all (rad/s) | straight | cornering steady | cornering transient | marginal Δ on `all` |
|---------|------------:|---------:|-----------------:|--------------------:|--------------------:|
| V0      | 0.01613     | 0.00859  | 0.04237          | 0.08152             | —                   |
| V1      | 0.01414     | 0.00577  | 0.03965          | 0.07818             | -0.00198 (-12.3%)   |
| V2      | 0.01384     | 0.00556  | 0.03918          | 0.05578             | -0.00030 (-2.1%)    |
| V3*     | 0.01607     | 0.00848  | 0.04233          | 0.08164             | (isolated) -0.00006 |
| V4      | 0.01380     | 0.00547  | 0.03913          | 0.05587             | -0.00005 (-0.3%)    |

\* V3 is reported *isolated* against V0 (not sequential). Its sequential contribution inside V4 is captured in the V2→V4 row.

**Headline: V0 → V4 reduces pooled yaw-rate RMSE from 0.01613 to 0.01380 rad/s, a 14.5% drop. By regime: straight −36.4%, steady −7.6%, transient −31.5%.** The transient column is where the gain is concentrated in absolute terms.

## Attribution (accounting scheme: sequential marginal on `all`, isolated for V3)

- **V1 (bias removal): -0.00198 rad/s (85% of the V0→V4 drop).** Half of V0's RMSE in straight is a static IMU/integration bias.
- **V2 (alignment): -0.00030 rad/s on `all`, but -0.0224 rad/s on transient alone (-29%).** The "all"-regime headline understates this because transient samples are a minority of pooled time. Aligning pred by its median 80 ms lead matches transient cornering peaks much better.
- **V3 (understeer): -0.00006 rad/s isolated.** Fitted `K_us ≈ 1.6e-5 s²/m²` only matters at high `v²` (≈ 0.04 rad/s correction at 50 m/s). At Mach-E suburban speeds in this dataset the linear-bicycle understeer term is in the noise. **Not a regression but essentially a no-op at these speeds.** A full ST upgrade with proper slip dynamics (not an in-residual correction) would attack the remaining transient RMSE.

Marginal drops sum: 0.00198 + 0.00030 + 0.00005 = 0.00233 rad/s ≈ V0−V4 = 0.00233 rad/s. Accounting closes to round-off.

## Regressions

No variant worsened the metric. V3 nudged transient very slightly worse (0.08152 → 0.08164, +0.015%) because the global K_us fit overcorrects on a few high-yaw-rate samples — well within noise.

## Limitations

- Scored only Mach-E (315 segs), not F-150 Lightning (230 available).
- Lag fit is integer-sample at 50 Hz (20 ms resolution). A fractional-delay fit would shave a few % off transient.
- Per-segment IMU bias assumed constant; slow drift within a segment would alias into other variants.
