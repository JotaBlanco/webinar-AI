# REPORT — KS lateral fidelity, Ford platforms

Module: `webinar-angle-B/modulo-1`
Date: 2026-05-26

## 1. Scope

Speed-known, lateral-only mode: `v` and `δ` are clamped to measured values; the
model only predicts the lateral channel (ψ̇, a_y, ψ, x, y). All work is on the
existing Ford sim CSVs (2 segments × 2 platforms, 2899 rows each @ 50 Hz);
rlog regeneration deps (cantools/pycapnp/zstandard) are absent in this env.

Reproduce:
```
cd webinar-angle-B/modulo-1
python3 run_ablation.py
```
Outputs: `ablation_results.csv`, `ablation_aggregate.csv`, `regime_breakdown.csv`.

## 2. Baseline residual

| Platform | Seg | n | RMSE ψ̇ [°/s] | RMSE a_y [m/s²] | corr ψ̇ | corr a_y |
|---|---:|---:|---:|---:|---:|---:|
| FORD_MUSTANG_MACH_E_MK1  | 1 | 2898 | 0.703 | 0.052 | 0.799 | 0.260 |
| FORD_MUSTANG_MACH_E_MK1  | 2 | 2898 | 0.128 | 0.071 | 0.955 | 0.883 |
| FORD_F_150_LIGHTNING_MK1 | 1 | 2898 | 1.369 | 0.585 | 0.918 | 0.896 |
| FORD_F_150_LIGHTNING_MK1 | 2 | 2898 | 0.753 | 0.223 | 0.998 | 0.936 |

Mean across segments:

| Platform | RMSE ψ̇ [°/s] | RMSE a_y [m/s²] |
|---|---:|---:|
| FORD_MUSTANG_MACH_E_MK1  | **0.416** | **0.061** |
| FORD_F_150_LIGHTNING_MK1 | **1.061** | **0.404** |

Regimes:
- Mach-E seg-1: near-constant **+0.70 °/s** yaw bias across all speed bands
  (residual std ≈ 0.06 °/s — bias dominates). No samples at v≥15.
- F-150 seg-1: highway (all v≥15). Mean residual is **−1.20 °/s** at |a_y|<1
  and **+1.64 °/s** at |a_y|≥1 (44 samples) — large lateral-channel miss
  during actual cornering.

## 3. Improvements proposed

1. **Per-platform bias correction** (yaw, a_y). Sensor offset / adapter
   sign-handling. Signal: non-zero residual mean. Measure: RMSE after mean
   subtraction on a hold-out segment.
2. **Linear single-track / understeer correction.** KS ignores speed-dependent
   yaw-gain droop. With openpilot-canonical m, l_f, l_r, C_α_{f,r}, the
   gradient `K_us = (m/L)·(l_r/Cf − l_f/Cr)` is positive for both Fords
   (rear-biased EVs with stiffer rear tyres). KS over-predicts ψ̇ at high v.
   Closed form: `ψ̇ = v·δ / (L + K_us·v²)`.
3. **Effective wheelbase refit.** Hypothesis: carParams wheelbase doesn't
   capture compliance / scrub. Closed-form LS on `1/L`.
4. **Steering compliance lag.** Column compliance + EPS lag delays actual
   road-wheel angle ~50–150 ms behind CAN. Cross-corr residual with dδ/dt.
   *Not implemented (time).*
5. **Non-linear tyre saturation at high |a_y|.** Above ~3 m/s² linear breaks
   down. F-150 seg-1 already shows sign flip at |a_y|≥1. *Not implemented.*
6. **Residual learning (small MLP/GP on v, δ, dδ/dt).** Upper-bound benchmark
   for a hybrid model. *Not implemented.*

## 4. Implemented variants + ablation

Variants 1, 2, 1+2, 3 implemented. Scalars (bias, L_eff) fit on **seg-1** per
platform; both segments evaluated. Mean RMSE across both segments:

| Platform | Variant | RMSE ψ̇ [°/s] | Δ vs baseline | RMSE a_y [m/s²] | Δ vs baseline |
|---|---|---:|---:|---:|---:|
| Mach-E  | baseline           | 0.416 | —      | 0.061 | —      |
| Mach-E  | + yaw/ay bias      | 0.420 | +1%    | 0.047 | −23%   |
| Mach-E  | + linear ST        | 0.409 | −2%    | 0.059 | −4%    |
| Mach-E  | + linear ST + bias | 0.410 | −1%    | 0.046 | −25%   |
| Mach-E  | wheelbase refit    | 0.939 | +126%  | 0.260 | +327%  |
| F-150   | baseline           | 1.061 | —      | 0.404 | —      |
| F-150   | + yaw/ay bias      | 0.733 | **−31%** | 0.456 | +13% |
| F-150   | + linear ST        | 0.848 | −20%   | 0.311 | **−23%** |
| F-150   | + linear ST + bias | **0.566** | **−47%** | 0.363 | −10% |
| F-150   | wheelbase refit    | 2.345 | +121%  | 0.401 | −0%    |

Per-segment table in `ablation_results.csv`.

## 5. Ranking

1. **Linear ST (understeer correction).** Pure physics, zero per-segment
   calibration, generalises across segments, ~20–25% RMSE drop on F-150 and
   no regression on Mach-E. **Keep — ship this.**
2. **Per-platform bias subtraction.** Big win on F-150 (−31% ψ̇) but on
   Mach-E the seg-1 bias does *not* generalise — applying it raises seg-2
   RMSE from 0.128 to 0.776. The bias is per-drive, not per-platform.
   **Do not deploy as a static constant**; consider online bias estimation
   (e.g. low-pass of residual when |δ|<small and v<low).
3. **Effective-L refit.** Destructive. The closed-form LS divides by
   `Σ(v·tan δ)²` which is tiny in highway driving — fitted L blows up
   (Mach-E 0.68 m, F-150 13.1 m) and over-corrects everywhere else. Wrong
   objective; needs regularised, regime-weighted fit. **Drop.**

Best combined result: F-150 with linear-ST + bias hits **0.57 °/s** vs
baseline 1.06 °/s (−47%). On Mach-E the linear-ST + bias variant takes a_y
from 0.061 to 0.046 m/s² (−25%) with ψ̇ unchanged.

## 6. Limitations

- Only 2 segments per platform — bias-generalisability question can't be
  answered (the Mach-E seg-1 vs seg-2 bias disagreement is the largest open
  question).
- Mach-E seg-1 has all v<15 m/s; seg-2 is statistically very different. The
  Mach-E aggregate is therefore noisier than F-150's.
- Closed-form ST steady-state ignores transient β̇ dynamics — under-predicts
  step-steer settling time. Acceptable since most samples are near steady.
- Persistent ~−0.37 m/s² mean a_y residual on F-150 seg-1 is suspicious —
  could be a road-bank / pitch-into-lateral compensator difference between
  the CAN signal and openpilot's pipeline. Could not verify without raw
  signal definitions outside the module.
- Could not regenerate sim CSVs (missing deps), so anything that changes the
  integrator semantics (δ lag filter, transient ST, etc.) is blocked. The
  variants here are all offline closed-form on the input columns.
