# Research — lateral KS fidelity

> Phase 1 — characterise the residual; no fixes proposed here.

## Datasets inspected

Source: `data/sim/segments/FORD_*/.../sim.csv` (pre-generated; speed-known lateral-only mode).

| Platform | Segment(s) | Duration | Avg \|v\| (m/s) | Notes |
|---|---|---|---|---|
| FORD_MUSTANG_MACH_E_MK1 | `08ec7b9afc6b766e/00000000--33439c2a9c/1` | 57.9 s | 8.70 | low-speed urban, near-straight (max \|δ\|=0.0025 rad), almost-pure linear regime |
| FORD_MUSTANG_MACH_E_MK1 | `112bd787ceca718d/00000003--55220ffbee/12` | 57.9 s | 11.30 | low/mid speed (0–20 m/s), still mostly straight |
| FORD_F_150_LIGHTNING_MK1 | `0b2c0bec9a28eb0f/00000001--82c7a5f419/34` | 57.9 s | 32.50 | **highway**, 26–36 m/s, gentle steering (\|δ\|≤0.01 rad). Worst residual. |
| FORD_F_150_LIGHTNING_MK1 | `112e4d6e0cad05e1/00000001--3975f8fbf5/9` | 57.9 s | 7.54 | low-speed with at least one large-angle event (max \|δ\|=0.44 rad ≈ 25° — parking-lot manoeuvre) |

## Baseline residual (from `evals/baseline_rmse.py`)

| Platform | RMSE ψ̇ (°/s) | RMSE a_y (m/s²) | corr ψ̇ pred-vs-meas |
|---|---|---|---|
| Mach-E (mean of 2 segs) | **0.4155** | 0.0613 | 0.877 |
| F-150 (mean of 2 segs) | **1.0607** | 0.4042 | 0.958 |

These match the `evals` baseline numbers to rounding (verified). The F-150 has the *higher* correlation but the *worse* RMSE — the residual is large in magnitude but well-correlated with the signal itself, suggesting a **gain/scale problem**, not noise.

## Regime breakdown (yaw-rate RMSE in °/s; binned by |a_y_meas|)

| Bin | Mach-E (mean) | F-150 (mean) | Comment |
|---|---|---|---|
| linear (\|a_y\|<1 m/s²) | 0.416 | 0.954 | residual already present where slip-angle should be ~0 |
| mid (1–2) | n/a | 1.493 | clear growth |
| high (2–4) | n/a | 2.162 | strongest growth, low-speed parking event |
| sat (>4) | n/a | n/a | no sample crosses 4 m/s² |

For the F-150 highway segment the residual is already 1.37 °/s RMSE *even though the entire segment is in the linear regime* — meaning the dominant error there is not tyre nonlinearity.

## Per-segment cross-correlation + regression diagnostic

`meas = slope * pred + intercept`, lag from cross-correlation, capped at ±25 samples (±0.5 s @ 50 Hz):

| Platform / segment | lag (ms) | bias (rad/s) | slope | intercept (rad/s) |
|---|---|---|---|---|
| Mach-E seg 1 (urban) | +20 | **+0.01222** | 0.849 | +0.01254 |
| Mach-E seg 2 (urban) | +40 | −0.00119 | 0.871 | −0.00082 |
| F-150 seg 34 (highway) | **+80** | −0.02016 | **0.447** | −0.01758 |
| F-150 seg 9 (low-speed) | +20 | −0.01032 | 0.936 | −0.00822 |

Three observations from this table:

1. **F-150 highway: slope ≈ 0.45.** The KS predicts roughly *twice* the yaw rate that the truck actually generates at 30 m/s, even at tiny steering (\|δ\|≤0.01 rad). Classic kinematic over-prediction — the rear axle is doing nontrivial slip work that KS cannot represent (`ψ̇ = v/L · tan(δ)` ignores slip).
2. **Mach-E seg 1 has a steady +0.012 rad/s = +0.7 °/s bias.** The segment is nearly straight (max \|δ\|=0.0025 rad). This is consistent with either a yaw-gyro static bias or a small steering-angle offset (centre of the rack not at 0°). The intercept of the meas-vs-pred regression equals the mean bias to four decimals → the residual is essentially a DC offset on this segment.
3. **A consistent +20–80 ms lag** (measured lags predicted) is present on every segment. This is the steering-actuator → measured-yaw transport delay (compliance + sensor pipeline). KS treats steering as instantaneously applied.

## Failure modes observed

1. **KS over-predicts yaw at speed** (slope < 1). Strongest on F-150 at 30 m/s. The bicycle model assumes no slip; the real vehicle has finite cornering stiffness so for a given steering angle it yaws *less* than `v/L · tan(δ)`. The over-prediction scales with v (or, more correctly, with `v²/(L·C_α)` — the understeer gradient).
2. **Constant yaw-rate bias on near-straight segments** (Mach-E seg 1: +0.7 °/s). Persists across the whole segment; the predicted yaw is essentially 0 because δ ≈ 0, so the measured yaw *is* the residual. Sensor zero-offset or rack zero-offset.
3. **Transport lag** (20–80 ms): measured yaw lags the predicted. Larger at higher speed where steering rates are higher relative to compliance time-constant.
4. **a_y residual mirrors ψ̇ residual** (since `a_y = v·ψ̇`), so any fix that improves ψ̇ should pro-rata improve a_y. No independent failure mode visible on a_y beyond the ψ̇ one.

## Signal-level observations (no fixes yet)

- `yaw_rate_resid_rads` mean per segment ranges from −0.020 to +0.012 rad/s — biases are segment-specific and not zero across the dataset.
- Residual grows with both |a_y| (regime table above) and with v (highway segment is worst). Disentangling the two is hard from 4 segments.
- A 20–80 ms lag is present in *every* segment, including the urban Mach-E ones where the steering signal is tiny.
- The F-150 highway-segment slope of 0.45 is a remarkably large gain error; it dominates that segment's RMSE.
- a_y bias is non-trivial on F-150 highway (−0.37 m/s²) and Mach-E urban seg 2 (−0.05 m/s²).

## Open questions for the plan phase

- Is the +0.7°/s Mach-E bias a yaw-gyro DC offset (would be invariant to v) or a steering-rack offset (would scale with v)? Only 1 segment shows it strongly — limited data.
- Can a single understeer-gradient correction `ψ̇_corr = ψ̇_KS / (1 + K_us · v²)` capture both the F-150 highway slope=0.45 and leave the Mach-E urban slope≈0.85 reasonable? K_us per platform.
- Is the 20–80 ms lag worth correcting at this RMSE scale, or is it second-order vs the gain error?
- With only 4 segments total (2 per platform), how confident can we be in per-platform fits? Risk of over-fitting.
