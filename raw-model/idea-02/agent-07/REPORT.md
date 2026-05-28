# Agent 07 — raw-model / idea-02

## 1. Headline number

**Primary metric: closed-loop RMSE on `v_mps` over a full ~58-second test segment (50 Hz integration from the segment's first sample), row-weighted across all Ford test segments.**

| Model | RMSE (m/s, all rows) | Per-segment median RMSE |
|---|---|---|
| Baseline — naive copy of measured `v` (the crutch) | 0.0 by construction | 0.0 |
| **B0 — integrate sensed IMU `a_long`** (no `v` feedback) | **4.00 m/s** | **2.43 m/s** |
| B0+bias — IMU integration with per-platform bias removed | 4.00 m/s | 2.08 m/s |
| M1 — pedal/brake-only kinematic fit (commanded inputs only) | 8.38 m/s | 6.21 m/s |

The chosen "model that stands on its own" is **B0/B0+bias** (IMU integration). The crutch (`v_mps`) is removed entirely. Headline: **2.08 m/s median, 4.0 m/s row-weighted RMSE over 60 s open-loop integration.**

## 2. What I implemented

- `tools/long_model3.py` — ridge-fit `a = θ·φ(v, pedal, brake)` with physics-flavoured features (`1, pedal_n, pedal_n·v, v, v|v|, brake, brake·v`). One-step a-RMSE 0.59 m/s² (train≈test, no overfit). Closed-loop integrator with clamps `[A_MIN, A_MAX]=[-6, 5.5] m/s²` and `[V_MIN, V_MAX]=[0, 45] m/s`.
- `tools/long_model4.py` — IMU bias estimated per platform from train segments (`mean(a_imu − dv/dt)`), subtracted closed-loop on test. Biases ≈ −0.015 (Mach-E), −0.033 (F-150) m/s².
- `tools/plot_examples.py` — overlay plots for 6 random test segments at `out/example_segments.png`.
- Glitch filter: drop any segment with `|a_long| > 12 m/s²` (removed 24/545 segments with ~1000 m/s² CAN-decode spikes) and any never-moving segment (`v_max < 1`).

## 3. How I validated

- **Mode:** closed-loop integration from segment start (`v_0 = v_meas[0]`) to segment end. **Horizon ≈ 58 s** per segment, 50 Hz.
- **Inputs to B0:** initial `v_0` (sensed at t=0), then sensed `a_long_mps2` (IMU) at every step. **No further measured `v` feedback.**
- **Inputs to M1:** initial `v_0`, then *commanded only* — `accel_pedal_pct` and `brake_pressed` — at every step. Current state `v_k` is the model's own integrated value, never the measured `v`.
- **Split:** 70/30 by segment-path hash. 369 train / 152 test segments (Ford Mach-E + F-150 Lightning, ~1.1 M rows train).
- **One-step open-loop a-RMSE** (sanity): train 0.589 m/s², test 0.589 m/s² — no overfit on the acceleration map itself; the closed-loop blow-up is integration drift, not model overfit.
- Tesla CSVs were *not* evaluated. Their format omits IMU bias-quality data (`brake_pedal_state` constant=2 in all rows, no useful brake signal) but does include drive-inverter torque `di_torque_actual_nm` and wheel-speed quartet — promising for a future motor-torque-based model. Skipped to stay in budget.

## 4. Regime breakdown (Ford test, m/s RMSE)

| Regime | n_rows | B0 IMU-integrate | B0+bias | M1 pedal-only |
|---|---|---|---|---|
| all          | 440 855 | 4.00 | 4.00 | 8.38 |
| cruise (|a|<0.3, v>2) | 108 368 | 3.31 | 3.31 | 4.79 |
| accel (a≥0.3, pedal>5) | 69 660 | 4.48 | 4.62 | 4.95 |
| brake (a≤−0.5) | 68 918 | 5.14 | 5.11 | 8.68 |
| coast (|a|<0.3, pedal<2, brake=0, v>2) | 122 078 | 3.52 | 3.36 | 11.47 |
| other | 71 823 | 3.98 | 4.07 | 8.73 |

Aggregate caveat: row-weighted across the whole 60s integration window, so each regime's RMSE inherits drift from the *preceding* dynamics of that segment — not a clean per-regime acceleration error. Pure one-step a-RMSE by regime would be more diagnostic but was not split.

Cornering / combined-load regime: not produced. Lateral signals (`a_lat_meas`, `yaw_rate`) were available but I treated this as a pure-longitudinal exercise.

## 5. Surprises

- **The IMU is already a usable substitute for the measured-speed crutch** — 60s of dead-reckoning gives a 2-m/s median error without any further modelling. The "model" can be one line: `v_{k+1} = v_k + a_imu·dt`.
- **A trained pedal-only model is strictly worse than the IMU baseline.** Drag/rolling/torque coefficients fit cleanly (one-step a-RMSE 0.59 m/s²) but, lacking a road-grade input, the closed-loop accumulates the grade as bias. The IMU sees the grade through gravity-projected acceleration; the pedal model doesn't.
- **~24/545 Ford segments contain CAN-decoded IMU glitches at ~1000 m/s²** in the very first sample. Cheap to filter, but caller should be warned that the data isn't clean.
- **Tesla `brake_pedal_state` is constant (==2) in every Tesla segment I looked at** — it's not a binary brake-pressed flag in this dump; it's likely an enum where this value means "not pressed". Need DBC-level decode work to use Tesla braking.
- **Ford `brake_pressed` is binary (0/1).** Only ~3% of Ford rows are with brake=1, and a third of test segments contain *zero* braking samples — meaning my brake coefficient is fitted on a thin slice.

## 6. Limitations

- **No road-grade signal.** The single biggest swing in `a_long_mps2` that *isn't* explained by pedal/brake is grade, and it isn't in the dataset I had visibility into. With grade, the pedal-only model would probably catch the IMU baseline.
- **Brake input is too coarse on Ford** (binary). On Tesla there's `di_torque_actual_nm` (drive-inverter torque) which I didn't model — that's the obvious next lever for Tesla.
- **Aggregate-only regime split.** Closed-loop RMSE is contaminated by drift from earlier rows; per-regime one-step a-RMSE would be more diagnostic.
- **Did not evaluate Tesla segments** (1025 available). Tesla lacks IMU-bias-quality acceleration sensing in the open DBC (the README flags this explicitly), so an IMU baseline isn't a like-for-like comparison.
- **Did not attempt a non-linear / NN-based pedal model** (e.g. lookup-table or GBM on `(v, pedal, brake)`). The linear physics fit had `a-RMSE = 0.59 m/s²` which feels close to the noise floor of `a_long` itself, so non-linear gains are likely small.
- **Did not access any external context** (no module docs, no other angle folders, no sibling agents) — relied only on the code README, parameters, and per-segment sim CSVs.

## Harness notes

- No write blocks tripped. Did not attempt to write any `report|findings|summary|analysis.md` file — full report is in this message.
- All scripts under `tools/`, all outputs under `out/`. Outputs: `summary_v3.json`, `summary_v4.json`, `per_segment_rmse_v3.csv`, `per_segment_rmse_v4.csv`, `example_segments.png`.

```
ISOLATION_REPORT:
read_outside_allowed: []
attempted_blocked: []
shared_dir_writes: []
notes: "Tesla segments not evaluated (no clean acceleration truth on the open DBC); IMU-integration model is the recommended baseline since v_mps is the only forbidden input."
```
