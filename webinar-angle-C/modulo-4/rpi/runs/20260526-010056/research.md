# Research — lateral KS fidelity

> Phase 1. Characterise the residual. No fixes.

## Datasets inspected

| Platform | Segment(s) | Duration | Avg \|v\| (m/s) | Notes |
|---|---|---|---|---|
| FORD_MUSTANG_MACH_E_MK1 | `08ec7b9.../1`, `112bd78.../12` | 57.9 s each | 8.70 / 11.30 | low-speed urban; max v = 20.2 m/s |
| FORD_F_150_LIGHTNING_MK1 | `0b2c0be.../34`, `112e4d6.../9` | 57.9 s each | 32.50 / 7.54 | one highway, one urban — mix |

n=2898 rows per segment, 50 Hz, ~58 s of CAN-derived sim data each. 4 Ford segments total.

## Baseline residual (mean across segments — matches `evals/baseline_rmse.py`)

| Platform | RMSE ψ̇ (°/s) | RMSE a_y (m/s²) | corr ψ̇ pred-vs-meas |
|---|---|---|---|
| Mach-E | 0.4155 | 0.0613 | 0.877 |
| F-150  | 1.0607 | 0.4042 | 0.958 |

Cross-checked against skill `baseline-residual/compute.py` — agrees to printed precision.

## Schema-check finding (sensor caught it)

`evals/schema_check.py` reports one of the Mach-E baseline CSVs (`112bd78.../12/sim.csv`) FAILS the `a_y_resid = meas − pred` invariant at max diff 1.0000003e-6, i.e. exactly on the 1e-6 tolerance boundary (floating-point noise from CSV round-trip). The CSV is upstream-generated, not ours — but we have to be aware that the schema_check threshold is brittle to FP round-tripping. For our own variants we will write residuals with enough precision to pass.

## Regime breakdown (pooled across segments per platform)

`yaw_rate_resid_rads` distribution, binned by velocity and |a_y|:

| Bin | Mach-E RMSE ψ̇ (°/s) | Mach-E mean (°/s) | F-150 RMSE ψ̇ (°/s) | F-150 mean (°/s) |
|---|---|---|---|---|
| v in [0,5) | 0.268 | +0.111 | 0.530 | -0.458 |
| v in [5,10) | 0.680 | +0.637 | 2.074 | -1.905 |
| v in [10,15) | 0.505 | +0.332 | 0.637 | -0.550 |
| v in [15,20) | 0.159 | -0.118 | 0.739 | -0.633 |
| v ≥ 20 | 0.132 | -0.087 | 1.369 | -1.155 |
| \|a_y\| in [0,1) | 0.505 | +0.316 | 1.054 | -0.854 |
| \|a_y\| in [1,2) | — | — | 1.419 | -0.531 |
| \|a_y\| in [2,3) | — | — | 2.162 | -2.104 |

Pooled mean residual: Mach-E **+0.32 °/s**, F-150 **−0.87 °/s**. Both materially non-zero ⇒ a constant-bias term is plausible (variant-A candidate, yaw-bias-correction skill).

Per-segment means inside Mach-E flip sign (+0.70 vs −0.07 °/s) — bias is not strictly constant within the platform; it drifts segment to segment. Within F-150 both segments share sign (−1.16, −0.59) so the platform-level bias is more honest there.

## Failure modes observed

1. **Prediction leads measurement by 60-80 ms.** Cross-correlation of `yaw_rate_meas` vs `yaw_rate_pred` peaks at lag ≈ −3..−4 samples (50 Hz) on every segment. Best-lag correlation lifts Mach-E seg-1 from 0.80 → 0.81 and barely moves the F-150 ones. Physically this is consistent with **steering compliance / actuator lag** — the road wheel responds slower than the recorded steering wheel signal. A first-order lag on `delta_road_rad` would absorb it. Magnitude small but consistent.
2. **F-150 residual scales with |a_y|.** corr(resid_yaw, |a_y|) = −0.88 on the high-speed F-150 segment. Sign is "more lateral G ⇒ more negative residual" ⇒ model **over-predicts** yaw rate at high G ⇒ classic **understeer-gradient / tyre cornering compliance** — the kinematic model assumes wheels point where the car goes, real tyres develop slip angles that subtract from yaw response. RMSE jumps from 1.05 → 2.16 °/s in the |a_y|∈[2,3) bin. This is the dominant failure mode on F-150 at speed.
3. **Persistent yaw-rate bias.** Pooled means are large multiples of the noise floor. Mostly likely candidates: (i) IMU zero-rate offset upstream, (ii) wheelbase miscalibration, (iii) a CAN-frame convention slip somewhere upstream. Whatever the cause, removing the per-platform mean is a "free lunch" if the residual is bias+noise.
4. **Mach-E corr is 0.877 — much weaker than F-150's 0.958** despite *smaller* RMSE. Smaller residual in absolute terms but the *shape* match is worse. Mach-E lives in low-speed urban driving where small `δ` ⇒ small `ψ̇`, and signal-to-noise is poor; "shape error" largely doesn't matter at this magnitude.

## Signal-level observations (no fixes yet)

- `mean(resid)` non-zero on both platforms ⇒ bias candidate. Sign: Mach-E +, F-150 −.
- Residual grows with |a_y| **on F-150 only**. Mach-E doesn't see enough lateral G (max \|a_y\| < 1 m/s²) to test the tyre-stiffness hypothesis.
- Slight pred-leads-meas lag on both platforms (~60-80 ms).
- F-150 corr ≈ 1 ⇒ shape is right ⇒ a gain+bias correction has headroom.

## Open questions for the plan phase

- Bias correction is the canonical variant-A (and there's a skill for it). Should I run it even though I suspect within-Mach-E sign flip means it'll under-perform for Mach-E? **Yes** — that's the value of the ablation: prove it doesn't always help.
- Variant B: actuator-lag delta correction (apply ~80 ms lead to delta_road) vs cornering-stiffness term scaling pred by `1 − k·|a_y|`. The understeer term targets the dominant F-150 failure mode and is well-motivated by signal (corr = −0.88). The lag fix is small. **Pick the understeer correction.**
- Sample size is tiny (2 segs × 2 platforms). Anything we measure is segment-conditional. Report it that way.
