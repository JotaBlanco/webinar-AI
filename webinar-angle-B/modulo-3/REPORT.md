# Lateral fidelity of the KS model — Ford platforms

Module: `webinar-angle-B/modulo-3`
Reproduce: from this directory, `python3 ablation.py` (aggregate) and
`python3 ablation_dynamic.py` (per-segment).

## TL;DR

- Baseline KS yaw-rate RMSE: **0.51 °/s** on Mach-E, **1.10 °/s** on F-150
  (aggregate over 2 segments × ~2898 samples each).
- The most informative segment (`F-150 / 9`, |δ_road|_max=25.4°,
  |ψ̇|_max=27.8°/s) drops from **0.75 °/s (KS) → 0.57 °/s (ST steady-state)
  → 0.31 °/s (ST + per-segment yaw-rate de-bias)**: a **59% reduction** on the
  only segment that actually exercises the lateral model.
- The other three segments are essentially straight-line highway driving
  (|δ_road| < 0.6°), so the headline RMSE is dominated by a yaw-rate sensor
  bias that swamps the KS model error. On those segments, ST contributes
  ~nothing and a per-segment bias removal does most of the work.

## 1. Baseline residual table (KS, speed-known lateral-only)

| Platform | Segments | N rows | RMSE ψ̇ (°/s) | RMSE a_y (m/s²) | corr ψ̇ | corr a_y | mean ψ̇ resid (°/s) |
|---|---|---|---|---|---|---|---|
| FORD_MUSTANG_MACH_E_MK1 | 2 | 5796 | **0.505** | 0.062 | 0.46 | 0.80 | +0.32 |
| FORD_F_150_LIGHTNING_MK1 | 2 | 5796 | **1.105** | 0.443 | 0.99 | 0.79 | −0.87 |

Non-zero mean residual on both platforms is the smoking gun for yaw-rate
sensor offset / sign-correlated tyre-compliance bias. corr ψ̇ for Mach-E is low
(0.46) because both Mach-E segments are nearly straight: little signal.

### Regime breakdown (KS baseline, F-150)

| Bin | N | RMSE ψ̇ (°/s) |
|---|---|---|
| v ∈ [0,10) m/s | 1573 | 0.79 |
| v ∈ [10,20) m/s | 1325 | 0.70 |
| v ∈ [20,30) m/s | 712 | 1.17 |
| v ∈ [30,50) m/s | 2186 | 1.43 |
| |a_y| ∈ [0,1) m/s² | 5485 | 1.05 |
| |a_y| ∈ [1,2) m/s² | 178 | 1.42 |
| |a_y| ∈ [2,4) m/s² | 133 | 2.16 |
| |δ_road| ∈ [6,30)° | 254 | 1.62 |

Monotonic growth with v and |a_y| — textbook KS-vs-ST gap.

### Per-segment

| Platform | Seg | |δ|_max | |ψ̇|_max | KS | ST | KS+bias | ST+bias |
|---|---|---|---|---|---|---|---|
| Mach-E | 1 | 0.14° | 1.18°/s | 0.703 | 0.708 | 0.064 | 0.063 |
| Mach-E | 12 | 0.31° | 1.25°/s | 0.128 | 0.110 | 0.116 | 0.114 |
| F-150 | 34 | 0.57° | 2.93°/s | 1.369 | 1.125 | 0.735 | 0.385 |
| F-150 | 9 | **25.39°** | **27.84°/s** | 0.752 | 0.572 | 0.490 | **0.307** |

## 2. Proposed improvements

1. **ST steady-state (understeer-gradient form).** `ψ̇_ss = (v/L)·δ / (1 + K_us·v²)`
   with `K_us = m·(l_r·C_α,r − l_f·C_α,f) / (L²·C_α,f·C_α,r)`. Hypothesis: KS
   over-predicts because it ignores tyre slip. Signal: KS residual grows
   monotonically with v and |a_y|. Measure: swap predictor, recompute RMSE.
2. **Yaw-rate sensor de-bias.** Hypothesis: gyro offset, per power-cycle.
   Signal: mean residual ≠ 0 even on |δ|≈0 samples; per-segment biases swing
   between +0.7 and −1.2 °/s. Measure: subtract straight-line mean from
   `ψ̇_pred` per segment.
3. **Full ST dynamic (β as a state).** Hypothesis: steady-state ST misses a
   first-order lag `τ ≈ m·v/(C_α,f+C_α,r)` during transients. Signal: lag
   between `δ̇` and `ψ̇_resid` on F-150 seg 9. Measure: integrate 2-state ODE
   and compare. Not implemented — time budget.
4. **Steering-ratio recalibration.** Hypothesis: `i_s` is non-linear vs
   |δ_wheel|. Signal: gain mismatch vs `|δ_wheel|`. Measure: fit `i_s_eff`
   per platform.
5. **Compliance lag in measured δ.** Hypothesis: rack lag of ~20-80 ms.
   Signal: cross-correlation peak shift. Measure: shift `δ_meas` forward,
   sweep for min RMSE.

## 3. Implemented changes + ablation

Implemented (1) and (2). Code: `ablation.py` (`predict_v0_ks`,
`predict_v2_st_steady`, `yaw_bias_offset`).

### Aggregate per platform

| Platform | Variant | RMSE ψ̇ (°/s) | Δ vs V0 | % vs V0 | RMSE a_y (m/s²) | Δ a_y |
|---|---|---|---|---|---|---|
| Mach-E | V0 KS | 0.505 | — | — | 0.062 | — |
| Mach-E | V1 KS+bias | **0.094** | −0.412 | **−81.5%** | 0.110 | +0.048 |
| Mach-E | V2 ST | 0.507 | +0.002 | +0.4% | 0.059 | −0.003 |
| Mach-E | V3 ST+bias | **0.092** | −0.413 | **−81.8%** | 0.109 | +0.047 |
| F-150  | V0 KS | 1.105 | — | — | 0.443 | — |
| F-150  | V1 KS+bias | 0.625 | −0.480 | −43.4% | 0.413 | −0.030 |
| F-150  | V2 ST | 0.892 | −0.213 | −19.3% | 0.323 | −0.121 |
| F-150  | V3 ST+bias | **0.348** | −0.757 | **−68.5%** | 0.319 | −0.124 |

### F-150 seg 9 only (the truly dynamic segment)

| Variant | RMSE ψ̇ (°/s) | Δ % | RMSE a_y (m/s²) |
|---|---|---|---|
| V0 KS | 0.752 | — | 0.223 |
| V2 ST | 0.572 | **−24.0%** | 0.226 |
| V1 KS+bias | 0.490 | −34.8% | — |
| V3 ST+bias | **0.307** | **−59.2%** | — |

K_us values: Mach-E ≈ 8.8e-4 s²/m² (factor at 25 m/s ≈ 0.65); F-150 ≈ 1.0e-3
s²/m² (factor at 25 m/s ≈ 0.61). Both positive (rear-biased), so ST always
pulls `ψ̇_pred` down — matches residual direction.

## 4. Ranking — what's worth it

| Rank | Change | Worth it? | Why |
|---|---|---|---|
| 1 | **ST steady-state (V2)** | YES | Genuine physics improvement. F-150 seg 9: ψ̇ RMSE −24%. Closed-form, ~zero runtime cost. Also slightly improves Mach-E a_y. |
| 2 | **Yaw-rate de-bias (V1/V3)** | YES, with caveat | Huge headline drop, but per-segment biases swing wildly — that is a sensor/power-cycle bias, not a model improvement. Fix in the adapter, not the model. Also degrades a_y at highway speed because a_y = v·ψ̇. |
| 3 | Full ST dynamic (β state) | Likely YES, not done | Should help transient bursts on F-150 seg 9. Out of budget. |
| 4 | i_s recalibration | Can't test | Insufficient |δ_wheel| sweep coverage in the available 4 segments. |

## 5. Limitations

- **Segment diversity is dominated by straight-line highway driving.** 3 of
  4 segments have |δ_road| < 0.6°. The aggregate ψ̇ RMSE is therefore
  dominated by a yaw-rate sensor bias, not by the lateral model. Headline
  numbers should not be reported externally without first regenerating with
  hand-picked dynamic segments.
- **Yaw-rate bias is per-segment, not a true model term.** The right fix
  lives in the adapter (subtract straight-line mean per power-cycle).
- **a_y degrades under V1/V3 on Mach-E.** Adding a constant to `ψ̇` propagates
  to `a_y = v·ψ̇`; at highway speed even ~0.01 rad/s of yaw bias becomes
  ~0.25 m/s² of a_y bias. Honest cost of the cheap fix.
- **Full ST dynamic model not implemented** — would require an `st_model.py`
  with integrated β and ψ̇ states. Time budget.
- **Could not regenerate sim CSVs** in this environment (`cantools`,
  `pycapnp`, `zstandard` not installed). Used the pre-generated CSVs.

## 6. How to reproduce

```bash
cd webinar-angle-B/modulo-3
python3 ablation.py            # aggregate ablation table per platform
python3 ablation_dynamic.py    # per-segment breakdown (highlights F-150 seg 9)
```

Inputs: `data/sim/segments/FORD_*/**/sim.csv` (symlinked, already-generated).
Outputs: stdout tables + `ablation_results.csv`.
