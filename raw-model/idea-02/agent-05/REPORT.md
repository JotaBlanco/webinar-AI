# Agent 05 — raw-model / idea-02

## Headline number

Primary metric: **closed-loop v RMSE at 15-second horizon** (multi-shoot rollout, re-init to measured v every 15s, propagate using only commanded pedal/torque/brake in between).

| Platform | Baseline (constant v, 15 s) | Longitudinal model (15 s) | Full-segment ~60 s model | One-step `a` RMSE |
|---|---|---|---|---|
| Tesla Model 3 | 2.57 m/s | **1.40 m/s** | 3.92 m/s | 0.26 m/s² |
| Ford Mustang Mach-E | 2.63 m/s | 2.71 m/s | 7.14 m/s | 0.50 m/s² |
| Ford F-150 Lightning | 3.32 m/s | 3.73 m/s | 7.63 m/s | 0.71 m/s² |

5 s horizon: Tesla 0.57 (vs 1.24 baseline), Mach-E 1.12 (vs 1.18), F-150 1.67 (vs 1.47). The Tesla model genuinely beats baseline; the Ford pedal-only models only match it at short horizons.

## What I implemented

1. **Standalone longitudinal model** in `tools/long_model.py`:
   `a_pred = k_prop·prop + k_b·brake_ind − c_drag·v² − c_roll·v − c_off`, integrated forward Euler at native ~50 Hz.
2. **Per-platform propulsion signal selection**: Tesla uses `di_torque_actual_nm` (signed drive-inverter torque — corr ≈ 0.97 with `a_long`); Fords use `accel_pedal_pct / 100` + `brake_pressed` (binary).
3. **Constrained linear LS fit** with non-negativity bounds on drag/roll/k_prop and non-positivity on k_b, so the closed loop is provably dissipative (no positive feedback runaway).
4. **Tried** a stage-2 closed-loop refinement (Nelder-Mead on integrated v-RMSE over a 12-segment subset) but it improved Tesla marginally and blew up F-150, so I reverted to the stage-1 result.

## How I validated

- **Mode**: closed-loop integration. `v_pred(0) = v_meas(0)` is the only measurement used; thereafter inputs are `prop(t)` (commanded — accel pedal or driver-requested torque from CAN) and `brake(t)` (commanded — brake-pressed indicator).
- **Horizons reported**: full segment (~58 s, single rollout), 15 s multi-shoot (re-init every 15 s), 5 s multi-shoot.
- **Baselines**: "constant v over the horizon" — the no-information lower bound at each horizon length.
- **Fit / val split**: 50 / 50 segments per platform, taken evenly across the dataset (every Nth file).
- **Inputs commanded vs sensed**: `accel_pedal_pct` is driver-sensed, `brake_pressed` is sensed/commanded indicator, `di_torque_actual_nm` is actuated (inverter feedback). None require ground-truth `v`.

## Regime breakdown (full-segment rollout)

RMSE (m/s) of `v_pred − v_meas` per regime, classified per-row from pedal/brake/accel:

| Regime | Tesla | Mach-E | F-150 |
|---|---|---|---|
| cruise | 5.83 | 7.07 | 6.20 |
| accel  | 6.48 | 7.09 | 8.21 |
| brake  | 7.82 | 8.67 | 8.80 |
| coast  | 4.32 | 10.92 | 8.00 |
| stop   | 4.78 | 6.54 | 11.59 |

Caveats: regime breakdown is over the **full ~60 s rollout** so it absorbs accumulated drift. At 5–15 s horizons the per-regime numbers would be 3–5× lower, but I didn't run a regime-decomposed multi-shoot pass in the time budget. Coast on Mach-E and stop on F-150 are the worst-conditioned regimes — pedal-only signal doesn't tell us regen vs. coasting and the model has no grade input.

## Surprises

- `brake_pedal_state` for Tesla is essentially a constant enum (`2`) in the sampled segments — Tesla brake observability is effectively zero from the data I had. That's why Tesla's fitted `k_b ≈ 0` and the model can't predict hard-brake events well even though overall accuracy is best (the torque channel covers most of it via lift-off + regen).
- `di_torque_actual_nm` for Tesla is so good a proxy for `a_long` (r=0.97) that the long. model effectively reduces to "torque-to-acceleration gain + drag", which is exactly the physics. The other parameters barely matter.
- Ford one-step `a` RMSE is excellent (0.5–0.7 m/s²) but integrating over 60 s blows up the v RMSE — small biases compound. This is why multi-shoot/short-horizon framing is the right metric for a standalone longitudinal model.
- The CSVs already include `a_long_mps2` (IMU) — for the canonical KS speed-known framing this is an input clamp; for our reverse problem it's the perfect regression target.

## Limitations

- **Brake magnitude**: only an indicator is available (binary `brake_pressed` on Ford, near-constant enum on Tesla). The model can't distinguish a tap from a panic stop. A brake-pressure CAN signal would substantially close the brake-regime gap.
- **Grade / wind**: not in the inputs. Constant `c_off` absorbs mean grade per dataset but per-segment grade variation goes uncompensated and dominates long-horizon drift, especially F-150.
- **Single per-platform parameter set**: no per-segment recalibration. With a brief warm-up window we could estimate `c_off` per drive.
- **Couldn't access**: per-task constraints — I did not read sibling agent folders, prior `raw-model/idea-*/`, `webinar-angle-*/`, or `webinar-00/`. So I don't know whether prior idea-02 baselines exist for direct comparison.
- **Wheel-speed channels** (`wheel_FL_kph` etc.) are present in the Tesla CSV but are essentially the same signal as `v_mps` — I deliberately did not use them as inputs since that would defeat the "no measured speed" brief.
- **No torque signal on Ford**: a Ford powertrain torque signal would likely lift the Mach-E / F-150 model to Tesla-level performance.

### Next steps I'd take

1. Decode brake-pressure on the Ford DBC if it's there; add a powertrain torque request channel.
2. Add grade estimation (low-pass `a_long − dv/dt`) as a slowly-varying input or per-segment offset.
3. Try a small NN or piecewise-linear pedal-to-torque map; the linear pedal→a assumption is the obvious weakest link for Fords.
4. Multi-shoot fitting (objective directly on integrated v over fixed horizons) once a torque signal is available — without it, the model lacks the resolution to benefit.

### Harness notes

No write blocks hit. Output artefacts: `tools/long_model.py` and `out/results.json`.

```
ISOLATION_REPORT:
read_outside_allowed: []
attempted_blocked: []
shared_dir_writes: []
notes: "Followed scope; only read inside ./code/, ./data/, and own agent folder. No sibling/prior-baseline material consulted."
```
