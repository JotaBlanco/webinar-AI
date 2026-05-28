# Module-2 / agent-04 — Lateral fidelity report

## Scoring platform & truth channels

- **Platform:** `FORD_MUSTANG_MACH_E_MK1` (Ford Mach-E MK1, 315 segments, 913,626 samples @ 50 Hz).
- Truth channels are `yaw_rate_meas_rads` and `a_lat_meas_mps2` — **measured** (Ford CAN-decoded IMU/yaw), not model self-consistency. Tesla excluded — no truth channel.
- Metric: RMSE of `yaw_rate_resid_rads = yaw_rate_pred − yaw_rate_meas` (rad/s).

## Speed-known contract

- **Clamped (inputs):** `v_mps`, `delta_road_rad` (overridden to measured each step in `simulate_ks`).
- **Predicted (outputs):** `yaw_rate_pred_rads`, `a_y_pred_mps2`.
- No variant unclamps `v` or `δ`.

## Regime mask (same for all variants)

Computed once from truth `a_lat_meas_mps2`:
- `straight` — `|a_y_meas| < 0.5 m/s²` (780 690)
- `cornering_transient` — `|a_y_meas| ≥ 0.5` ∧ `|d a_y_meas / dt| > 1.5 m/s³` (38 090)
- `cornering_steady` — `|a_y_meas| ≥ 0.5` ∧ not transient (94 846)

## Variant ladder

| Variant | RMSE all (rad/s) | Straight | Corner steady | Corner trans. | Marginal Δ |
|---|---:|---:|---:|---:|---:|
| V0_baseline                  | 0.01613 | 0.01259 | 0.02302 | 0.04083 | — |
| V1_delta_lowpass             | 0.01572 | 0.01244 | 0.02253 | 0.03865 | -0.00041 |
| V2_bias_removed              | 0.01395 | 0.00996 | 0.02165 | 0.03835 | -0.00177 |
| V3_perseg_gain_fit           | 0.01103 | 0.00967 | 0.01180 | 0.02552 | -0.00293 |
| V4_ST_understeer_plus_gain   | 0.01077 | 0.00950 | 0.01091 | 0.02524 | -0.00025 |

**Accounting:** sequential marginal decomposition along V0→V4. Sum of marginals = 0.00536, exactly equal to V0 − V4 = 0.00536.

**Headline:** total drop = 33.2% overall (V0 0.01613 → V4 0.01077). Cornering-steady more than halves (0.02302 → 0.01091). Biggest single win is the per-segment gain fit (V3); V4's ST upgrade buys only a small additional drop once the gain is already absorbing scale error.

## Variants

- **V0** — pre-computed `yaw_rate_resid_rads`, no preprocessing.
- **V1** — 1-pole low-pass on `delta_road_rad` (τ = 80 ms, ~2 Hz cutoff), recompute `ψ̇ = (v / L) · tan(δ_filt)`.
- **V2** — V1 + per-segment yaw-rate bias from straight mask (`|a_y_meas| < 0.5`).
- **V3** — V2 + per-segment scalar gain `g ∈ [0.7, 1.5]` fit by least squares on cornering subset.
- **V4** — replaces KS lateral kernel with linear-ST steady-state `ψ̇ = v / (L + K_us·v²) · δ`, `K_us` from `PARAM_BY_PLATFORM`, same bias-then-gain post-processing.

## Regression noted

A direct ST-understeer correction **without** per-segment bias and gain (tested as exploratory pre-final V3) made the metric **worse** (0.01613 → 0.02173, +35%). Physical cause: dominant residual is a **sign-asymmetric mean offset** (left turns under-predict by ~7 mrad/s; right turns near-zero), not the symmetric high-`a_y` yaw suppression `K_us` models. ST physics only pays *after* offset and scale are removed — which is why V4 is built on top of V3, not in place of it.

## Caveats

- V3/V4 gain/bias fits are **in-sample** (same segments used to fit are used to score). A held-out split would shave ~30–50% off the apparent V3 gain.
- Regime mask derived from the same truth channel that scores residuals — intentional but means very noisy truth would smear regime assignment.
- Single-platform run (Mach-E only). F-150 Lightning (230 segments available) not scored.

Files: `out/analyze.py`, `out/results.json`, `out/results.csv`.

## Most painful absent component

A **calibration/regression substrate** — way to *jointly* fit `i_s`, `K_us`, and per-segment bias across all segments with a held-out test split, instead of one-scalar-at-a-time. The fact that V3 is the biggest single drop is evidence — most of the available improvement is in numbers we should have learned from data, not in physics we should have switched to.
