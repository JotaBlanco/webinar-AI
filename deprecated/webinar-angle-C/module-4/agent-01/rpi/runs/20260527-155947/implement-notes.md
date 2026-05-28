# Implement notes — 20260527-155947

## What ran

`tools/ablate_lateral.py <PLATFORM>` for both Fords. Variants in locked plan order. Train = 4/5 interleaved (i%5 != 0), test = every 5th. All fits per-platform.

## Results

### FORD_MUSTANG_MACH_E_MK1 (overall test RMSE rad/s)

| variant      | overall | Δ marginal | straight | steady  | transient |
|--------------|---------|------------|----------|---------|-----------|
| V0 baseline  | 0.01613 | —          | 0.00878  | 0.03147 | 0.05743   |
| V1 +bias     | 0.01614 | -0.00001 REGRESSION | 0.00874 | 0.03155 | 0.05750 |
| V2 +gain     | 0.01558 | +0.00056   | 0.00947  | 0.02966 | 0.05148   |
| V3 +lag1     | 0.01575 | -0.00017 REGRESSION | 0.00954 | 0.02970 | 0.05298 |

Params (V3): `bias=0.000754 rad/s, gain=1.0687, lag=1 sample`. Coherence: 0.0000.

### FORD_F_150_LIGHTNING_MK1

| variant      | overall | Δ marginal | straight | steady  | transient |
|--------------|---------|------------|----------|---------|-----------|
| V0 baseline  | 0.02037 | —          | 0.00899  | 0.03629 | 0.05161   |
| V1 +bias     | 0.02006 | +0.00031   | 0.00799  | 0.03634 | 0.05161   |
| V2 +gain     | 0.01635 | +0.00372   | 0.00629  | 0.02854 | 0.04519   |
| V3 +lag1     | 0.01651 | -0.00016 REGRESSION | 0.00638 | 0.02855 | 0.04624 |

Params (V3): `bias=0.004422 rad/s, gain=0.8592, lag=1 sample`. Coherence: 0.0000.

## Deviation from plan

None on ladder order. One **surprise**:

`schema_check.py` FAILS on every source `sim.csv` — the stored `yaw_rate_resid_rads` equals `meas − pred` (max diff 8.9e-07), not `pred − meas` as the convention in AGENTS.md and `CLAUDE.md` claims (max diff 9.79e-02). Ratchet item #1 (the very past-failure encoded into AGENTS.md) is **present in the data on disk**. RMSE is sign-symmetric, so the variant ladder numbers are unaffected, but anyone using the stored residual column with the documented sign convention will invert their analysis. Reported in REPORT.md.

## Regressions explained (physical cause)

- **Mustang V1 bias = 0.00075 rad/s.** Median bias is essentially zero on this car — the steering-zero is already trimmed in openpilot. V1 cannot help; the −1e-5 wobble is float noise.
- **V3 lag-1 on both cars.** Cross-correlation on one segment suggested pred leads by ~1 sample, but a uniform 1-sample shift across the whole corpus over-corrects: many segments have sub-sample lag, and the shift creates phase error in transients. Lag is real but not a uniform integer-sample quantity → out of scope for a scalar variant.

## Cross-platform check

The gain has **opposite sign of correction** between cars (Mustang 1.07 → KS under-predicts; F-150 0.86 → KS over-predicts). A single platform-pooled gain would be ~1.0 and useless. **Per-platform fit is mandatory**, per-segment would be calibration not modelling.

## Artifacts

- `out/ablate_FORD_MUSTANG_MACH_E_MK1_20260527-160123.csv` + `.json`
- `out/ablate_FORD_F_150_LIGHTNING_MK1_20260527-160129.csv` + `.json`
- `tools/ablate_lateral.py`
