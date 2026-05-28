# Agent 10 — raw-model / idea-02

## 1. Headline number

Closed-loop integrated-speed RMSE over ~30s test segments:

| Platform | Baseline (const-a) | My model | Ceiling (measured a) |
|---|---|---|---|
| Tesla Model 3 | 7.13 m/s | **4.01 m/s** | 0.01 m/s |
| Ford F-150 Lightning | 7.89 m/s | **5.72 m/s** | 2.41 m/s |
| Ford Mach-E | 7.22 m/s | **7.13 m/s** | 4.75 m/s |

Open-loop one-step a_long RMSE (the cleaner metric): Tesla **0.25 m/s²** (56% skill vs std), F-150 **0.55** (22%), Mach-E **0.58** (24%).

## 2. What I implemented

- Linear regression `a_pred = k_th*aped + k_br*brake + k_v*v + k_v2*v² + k_off*liftoff + k_τ*τ_motor + b`, fit per platform on a hash-based 60/40 train/test split.
- Forward-Euler integration of `a_pred` to recover `v_pred` in closed loop (re-uses *its own* predicted v as the drag-feature input — no measured-v leakage).
- Tesla uses motor torque `di_torque_actual_nm` (the regen signal) since `brake_pedal_state` is unusable (constant=2 on every Tesla rlog).
- Baseline = constant `a = mean(a_long)`; ceiling = re-integrate measured `a_long`.
- Regime labels from measured a_long sign and pedal: cruise / accel / brake / coast.

## 3. How I validated

- **Open-loop one-step:** predict `a_long(t)` from features at time t; compare to measured `a_long(t)`. Inputs: commanded `accel_pedal_pct`, `brake_pressed` (or motor torque for Tesla), sensed current `v`.
- **Closed-loop integration:** integrate `a_pred` from initial `v(0)=measured`, feeding predicted v back into the drag term. Horizon = full segment (~30-60 s, 1500-3000 samples at 50 Hz). All inputs except the initial-condition v0 are commanded; v inside the loop is *self-consistent*, never the measured value. Pooled across 28-35 test segments per platform, length-weighted.

## 4. Regime breakdown

(model RMSE, m/s; closed-loop)

| Regime | Tesla | F-150 | Mach-E |
|---|---|---|---|
| cruise | 3.51 | 4.46 | 9.65 |
| accel  | 5.31 | 4.39 | 5.64 |
| brake  | 4.86 | 4.90 | 6.15 |
| coast  | 3.91 | 6.92 | 6.22 |

Coast is the worst for the Fords — regen behavior isn't captured by a pedal+brake feature pair alone. Tesla's cruise is best because torque sign correlates tightly with coast/regen.

## 5. Surprises

- **The "ceiling" is leaky.** Integrating Tesla's `a_long_mps2` reproduces v to 0.009 m/s RMSE because the adapter derives a_long *from* dv/dt on Tesla — it's not an independent IMU channel. The Ford ceiling is ~2.4 m/s (real IMU `VehLongComp_A_Actl`), showing how much drift a single integration of even good sensor data accumulates over 30 s.
- **Tesla brake signal is dead.** `brake_pedal_state` is constant=2 across every segment I sampled. Workshop docs say the party DBC doesn't surface a usable brake-pressed bit — Tesla braking only enters via the motor regen torque.
- **Mach-E barely beats baseline closed-loop** despite a reasonable open-loop fit (0.58 m/s² RMSE). The drift dominates — a 0.6 m/s² bias for 30 s = 18 m/s of v-error. This is a fundamental integration-of-noise problem, not a fit problem.

## 6. Limitations

- Per the harness, could not read sibling agents, prior `webinar-angle-*/`, `raw-model/idea-*/` (other than my own), or `webinar-00/`. Solution shaped from `code/_README.md` + adapter files only.
- No road-grade signal. The standing residual between IMU `a_long` and `dv_meas/dt` (mentioned in the README as containing "grade + powertrain + sensor bias") was not used; integrating an unbiased-a feature could probably halve the drift.
- Linear model only. A small MLP or gradient-boosted regressor on the same features would likely cut open-loop RMSE 30-50%, but I budgeted the linear baseline first.
- Train/test split is hash-by-segment-name; haven't checked for distribution shift across devices/dates.
- `np.linalg.lstsq` only — no regularisation. The Mach-E `liftoff`+`bias` pair show partial collinearity (signs cancel) which probably hurts generalisation.
- What I'd want next: (a) explicit grade decomposition from low-frequency IMU-vs-dvdt residual, (b) train a small NN on `[aped, brk, v, τ, last-a]` with a 1-2s look-back, (c) horizon-stratified RMSE (1 s / 5 s / full segment) to separate fit quality from integration drift.

Outputs: `out/long_model_summary.csv` plus three PNGs `out/long_model_<PLATFORM>.png`. Scripts in `tools/long_model.py` and `tools/plot_one.py`.

No harness write-block was hit (I avoided `report.md`/`findings.md`/etc; only wrote scripts under `tools/` and outputs under `out/`).

```
ISOLATION_REPORT:
read_outside_allowed: []
attempted_blocked: []
shared_dir_writes: []
notes: "Tesla a_long_mps2 is derived from dv/dt in the adapter pipeline, so the 'measured-a' ceiling for Tesla is a tautology — flagged in the report."
```
