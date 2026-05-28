# Module-2 / agent-04 (angle-B) — Lateral fidelity report

## Headline
**Lateral yaw-rate RMSE on FORD_MUSTANG_MACH_E_MK1 cut from 0.01613 rad/s → 0.01388 rad/s (-14.0%)** with two interpretable, physics-motivated post-corrections. A third (speed-dependent understeer) regressed and is reported honestly.

## Setup
- **Platform:** `FORD_MUSTANG_MACH_E_MK1` — 315 segments, 913 626 samples @ 50 Hz.
- **Truth column:** `yaw_rate_meas_rads` — measured from the Ford CAN IMU via `opendbc/ford_lincoln_base_pt` (not predicted, not self-consistency).
- **Contract:** `v` and `δ` clamped to measured. Only `ψ̇` (and `a_y`) are predicted. Contract not touched.
- **Regime mask:**
  - straight   : `|ψ̇_meas| < 0.05` rad/s → 816 709 rows
  - steady     : `|ψ̇_meas| ≥ 0.05` and `|δ̇| < 0.05` rad/s → 78 420 rows
  - transient  : `|ψ̇_meas| ≥ 0.05` and `|δ̇| ≥ 0.05` rad/s → 18 497 rows
- **Attribution:** strict marginal V0→V_last; sum = total by construction.

## Variant ladder

| Variant | Description | RMSE all | straight | steady | transient | Marginal Δ (all) |
|---|---|---:|---:|---:|---:|---:|
| V0 | Baseline KS, pred as-is | 0.01613 | 0.00859 | 0.03720 | 0.06099 | — |
| V1 | + per-segment yaw-rate bias removal (estimated on straight regime, applied everywhere) | 0.01461 | 0.00473 | 0.03704 | 0.06117 | -0.00151 |
| V2 | + global constant understeer/overcorrection gain `K* = 1.0903` on cornering | 0.01388 | 0.00560 | 0.03537 | 0.05318 | -0.00073 |
| V3 (regression) | + speed-dependent factor `1/(1 + K_us · v²)`, `K_us = 1.12e-4` | 0.01439 | 0.00411 | 0.03658 | 0.06170 | +0.00051 |

**Total V0 → V2 drop: 0.00224 rad/s (14.0%)**, of which 67% is per-segment bias (V1) and 33% is the gain term (V2).

## Physical interpretation

- **V1 bias** collapses straight-line residual by 45%. Mechanism: IMU mounting / wheel-alignment offset + small CAN-signal zero-error. Per-segment, not global — consistent with device-mount variability between routes.
- **V2 gain `K* = 1.09` (> 1)** means KS *underpredicts* cornering yaw rate by ~9% on average. **Not** the textbook "KS ignores slip" story (which would predict overprediction). It's consistent with drivers overcorrecting steering to compensate for tyre slip — the *measured* `δ` already includes that compensation, so `(v/L)·tan(δ)` carries a small extra factor under the clamp. Largest win on transient: -13%.
- **V3 speed dependence regressed** — gain mismatch is dominated by handling/driver style, not by `v²` understeer growth. Honest negative result.

## Painful absence

Measured **sideslip β** is missing — only computable via a kinematic-vs-GPS heading reconstruction (out of scope here). Would separate "model has no slip" from "driver overcorrects".

## Rule-prevented near-misses

- Almost reported V0 with a global bias subtraction — trap #9 (preprocessing belongs in V1+, not V0).
- Almost used Tesla because its segment count is 3× Ford — trap #1/#7 (Tesla has no truth).
- Almost "improved" by unclamping `δ` — trap #2 (would break contract).
- Almost used `delta_wheel_deg` in a quick check — trap #3, ~17× error.

## Most surprising

**`K* = 1.09 > 1`.** With `δ` clamped to measured, the textbook KS-overprediction story inverts: drivers' steering already contains slip-compensation, so the model **underpredicts** by ~9% in steady cornering. That inverts the standard "ST upgrade closes the gap" story for this contract.

Files: `out/analyze.py`, `out/summary.json`.
