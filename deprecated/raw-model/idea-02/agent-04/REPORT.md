# Agent 04 — raw-model / idea-02

Solid results. Out of time-budget safety I'll stop iterating and report. Note the headline: M2 physics-form is ~equal to M1 linear; closed-loop 10s RMSE drops from 1.52 m/s (constant-speed baseline) to ~0.69 m/s, a ~55% reduction. Open-loop one-step a-RMSE drops from 0.62 m/s² (predict zero) to 0.23 m/s² (predict from torque + pedal + v).

---

## 1. Headline number

- Primary metric: **closed-loop 10-second-window speed RMSE on held-out test segments (mean across windows)**
- Baseline (M0 = "predict zero accel", i.e. v(t) = v(0)): **1.52 m/s**
- Final (M2 physics-form longitudinal model): **0.69 m/s** (about a 55% reduction)
- Open-loop one-step acceleration RMSE: baseline 0.62 m/s² → M2 0.233 m/s² (62% reduction)

## 2. What I implemented

(in `tools/build_long_model.py`, outputs in `out/long_model_metrics.json`)

- **M0 baseline**: constant-speed predictor, ground truth for "do nothing".
- **M1 linear regression**: `a_pred = b0 + b1·T_motor + b2·pedal_pct + b3·brake_on + b4·v + b5·v²`, fit by OLS.
- **M2 physics-form**: `m·a = k_T·T_motor − c0 − c_rr·v − c_a·v² − k_b·brake_on·v` with vehicle mass `m = 2035 kg` (Tesla M3 LR, openpilot-canonical from `parameters.py`); 5 coefficients fit by OLS.
- Train/test: 200 Tesla Model 3 sim.csv segments, 80/20 split by segment id, ~580k rows.

## 3. How I validated

- **Open-loop one-step** mode: at each timestep, predict `a` from sensed/commanded inputs (motor torque, accel pedal, inferred brake, v) and compare to measured `a_long_mps2`. No integration.
- **Closed-loop integration** mode (the honest one): Forward-Euler integrate `v(t)` from `v(0)` using `a_pred(v_pred, u_t)`, with `u_t` = (motor torque, accel pedal %, inferred brake). Two horizons reported: full segment (~60 s) and 10-second windows (reset each window).
- Inputs at inference time: motor torque (`di_torque_actual_nm` — sensed actuator output, the closest stand-in for a torque command), accelerator pedal % (commanded), inferred brake (see surprise #1). The predicted `v` is fed back into the next step. `v_meas` is NEVER fed into the model except as v(0) at window start.

## 4. Regime breakdown

(closed-loop 10-s window RMSE in m/s; regimes assigned mutually-exclusively from `(a_long, pedal, v)`)

| regime | M0 | M1 | M2 |
|---|---|---|---|
| cruise | 1.93 | 0.86 | 0.86 |
| accel | 4.20 | 1.26 | 1.24 |
| brake | 5.01 | 1.17 | 1.14 |
| coast | 0.97 | 0.90 | 0.90 |
| stop | 3.32 | 1.32 | 1.33 |
| other | 2.83 | 1.03 | 1.00 |

The hardest regimes (accel and brake) get the biggest absolute improvement; the easiest (coast) gets the smallest because constant-speed is already pretty good. M1 and M2 perform nearly identically.

## 5. Surprises

- **`brake_pedal_state` is always 2 ("INVALID") in the dataset** — the DBC enum is `0=OFF, 1=ON, 2=INVALID`. So in the recorded comma3 passive logs there is no usable brake-on signal. I had to infer braking from negative `a_long`. This is a real data-quality landmine for any longitudinal modeller using these segments.
- **The physics fit produces an unphysical `c_rr = −4.22`** (rolling resistance coefficient should be positive). Almost certainly collinearity between motor torque and speed during cruise — when `T_motor` is balancing drag, the linear fit can shuffle credit between terms. The model still predicts well; the coefficients aren't individually trustworthy.
- **M1 (no physics) ≈ M2 (physics)** at this complexity. Both are linear in the inputs, so without nonlinear regime handling or actuator dynamics the physics structure isn't buying much over raw OLS.
- The codebase's `clamp_v_to_measured=True` mode in `ks_model.py` is exactly what the brief calls "the crutch" — confirmed by the docstring §"Speed-known framing".

## 6. Limitations

- No access checked outside the agent folder; honoured all restrictions.
- Used only Tesla Model 3 segments (1025 of 1570 available). 200-segment subsample for speed.
- Brake force is implicitly lumped with aerodynamic/coast drag, since brake_pedal_state is unusable. A working brake-pressure channel would let M2 fit a real `k_b`.
- Tried only linear/physics-linear forms. Likely gains from: (a) wheel-speed differential as a low-pass-filtered ground-truth for short-horizon drift correction, (b) gear/regen modelling on torque, (c) a nonlinear residual model (small MLP or a per-regime intercept), (d) RK4 instead of forward-Euler for the integrator.
- "Open-loop one-step" trains and tests on the same dataset's `a_long_mps2`, which was itself derived from smoothed `dv/dt`. So M1/M2 are partly being graded against a smoothed version of the target — the closed-loop number is the honest one.
- Did not try the Ford platforms (Mach-E, F-150 Lightning) — only Tesla M3.

Artefacts:
- `tools/build_long_model.py`
- `out/long_model_metrics.json`

No `REPORT.md` write was attempted — full report is above.

```
ISOLATION_REPORT:
read_outside_allowed: []
attempted_blocked: []
shared_dir_writes: []
notes: "brake_pedal_state is always =2 (INVALID enum) in these segments; braking inferred from negative a_long. Physics-form rolling-resistance coefficient came out negative — collinearity between motor torque and speed in cruise."
```
