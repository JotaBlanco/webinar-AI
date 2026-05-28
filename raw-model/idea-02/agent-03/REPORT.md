# Agent 03 — raw-model / idea-02

## 1. Headline number

**Primary metric:** mean MAE of predicted `v_mps` over a 30 s closed-loop horizon, averaged across 45 held-out test segments (3 platforms).

| | hold-v0 baseline | **V4 commanded-only model** | IMU-integrated (sensed) |
|---|---:|---:|---:|
| Closed-loop 30 s v MAE | **2.92 m/s** | **3.07 m/s** | 0.67 m/s |
| Closed-loop 10 s v MAE | 1.31 m/s | **1.18 m/s** | — |
| Closed-loop 5 s  v MAE | 0.76 m/s | **0.65 m/s** | — |
| Open-loop 1-step a MAE | 0.39 m/s² (predict 0) | **0.36 m/s²** | n/a |

At short horizons (5–10 s) the model beats hold-v0; at 30 s it slightly loses, mostly due to F-150 drift. Open-loop one-step `a_long` prediction beats the predict-zero baseline on all three platforms.

## 2. What I implemented

1. **Dataset builder** (`tools/build_dataset.py`): sampled 60 segments per platform from `data/sim/segments/`, kept `t_s, v_mps, a_long_mps2, accel_pedal_pct, brake`. Normalised the brake column across vehicles (Tesla `brake_pedal_state==2` always → degenerate; Ford `brake_pressed` 0/1). Stripped rows with `|a_long|>8 m/s²` (57 corrupted rows on F-150, one as high as 1058 m/s²). Final size: 522k rows, 180 segments.
2. **Per-platform fits** (`tools/fit_v3.py`, `fit_v4.py`):
   - V3 — physics-shaped linear: `a = c_t·pedal + c_b·brake − c_d·v² − c_r·v + bias`, drag/roll non-neg.
   - V4 — richer ridge LS with features `{pedal, pedal·v, pedal², brake, brake·v, v, v², 1}`.
3. **Closed-loop simulator**: forward-Euler `v[k+1] = max(0, v[k] + a_pred·dt)` with `a` clipped to `[−8, +6] m/s²` and `v` clipped to `[0, 80] m/s` for numerical stability.

## 3. How I validated

- **Modes:** both. (a) Open-loop one-step `a` prediction (fed measured `v`, `pedal`, `brake` at each step and scored against measured `a_long`). (b) Closed-loop integration starting from `v0 = v_meas[0]`, fed commanded inputs `(pedal_pct, brake)` only — model integrates its own `v` forward.
- **Horizons:** 5, 10, 20, 30 s; primary headline reports 30 s.
- **Inputs to closed-loop V4 model (all commanded / driver):** `accel_pedal_pct`, `brake` indicator, plus its own simulated `v`. No `a_long`, no IMU, no measured `v` after step 0.
- **Reference baselines:** "hold v0" (no model), and "integrate measured `a_long`" (uses sensed IMU — upper bound a longitudinal model could realistically approach).
- **Split:** 75/25 by segment ID (135 train / 45 test segments).

## 4. Regime breakdown (open-loop a, test set)

| Platform | regime | n | a_mae (V4) | predict-zero MAE |
|---|---|---:|---:|---:|
| F-150 | accel | 5009 | **0.31** | 0.90 |
| F-150 | brake | 2579 | **1.19** | 1.54 |
| F-150 | coast | 8877 | 0.26 | 0.20 |
| F-150 | cruise | 17506 | 0.23 | **0.10** |
| F-150 | stopped | 7027 | 0.21 | **0.27** |
| Mach-E | accel | 4533 | **0.35** | 1.03 |
| Mach-E | brake | 3884 | **1.22** | 1.75 |
| Mach-E | coast | 4299 | **0.19** | 0.22 |
| Mach-E | cruise | 16067 | 0.28 | **0.10** |
| Tesla | accel | 6551 | **0.36** | 0.85 |
| Tesla | brake | 1912 | **1.14** | 1.47 |
| Tesla | coast | 7252 | **0.20** | 0.25 |
| Tesla | cruise | 23213 | 0.14 | **0.10** |

Model wins on the high-energy regimes (accel, brake) where it matters most; loses to predict-zero in cruise/stopped where the truth is already near zero.

## 5. Surprises

- **F-150 IMU outliers:** raw `a_long_mps2` contained values up to 1058 m/s² (57 rows). One unfiltered fit drove `c_drag` to a runaway value and made closed-loop integration overflow to `inf`. Filter at 8 m/s² fixed it.
- **Tesla brake never decoded:** `brake_pedal_state` is constant 2 across the entire Tesla dataset I sampled. The Tesla brake signal is effectively missing — model has no way to know about friction-brake events on Tesla, only regen-via-pedal-zero.
- **EV regen dominates "coast":** model-zero baseline MAE on coast is small (~0.2 m/s²) but only because mean deceleration is small in this label; in real EVs the regen torque varies with v in ways a linear model captures only crudely.
- **Pedal % is not the actual command.** The model has no access to motor torque (Tesla has `di_torque_actual_nm` for some segments — Ford does not). Pedal % is a driver-facing surrogate that maps non-linearly to torque depending on Sport/Comfort mode and v.

## 6. Limitations

- **Not allowed to read** any sibling agent folder, any `webinar-angle-*/modulo-*/`, any other `raw-model/idea-*/`, or `webinar-00/`. I obeyed; this means I had no prior longitudinal-model framing to draw on.
- **Tesla brake signal is dead** in the data I had access to — I could not learn friction-brake response separately from regen on Tesla.
- **No grade / road slope.** A constant per-segment grade explains a chunk of the open-loop residual; I didn't fit per-segment offsets.
- **No motor torque feature for Ford.** I saw Tesla `di_torque_actual_nm` exists in one column but didn't unify it (not present in Ford CSVs).
- **Closed-loop accumulation hurts at 30 s** — a recurrent or residual-corrected integrator would help. Next iteration would be: (a) trust-region correction using current `v_meas` periodically (semi-open-loop), (b) GP / small MLP for the residual, (c) per-platform mass + drag from `parameters.py` to constrain the coast slope.
- **Files written:** under `tools/` and `out/` only. No writes to `code/` or `data/`. No `report.md` write attempted (kept this report in-line per instructions).

```
ISOLATION_REPORT:
read_outside_allowed: []
attempted_blocked: []
shared_dir_writes: []
notes: "Only read files inside ./code, ./data, and my own agent-03 folder; outputs under tools/ and out/. F-150 raw a_long contained extreme outliers (max 1058 m/s²) that required filtering."
```
