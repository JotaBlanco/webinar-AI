# Agent 08 — raw-model / idea-02

Ford pedal/brake channels are degenerate (always 0). So for Ford the only "input" available would be IMU `a_long` itself, which is essentially the derivative of v — that's still a crutch. So we honestly can't build a non-crutch longitudinal model for Ford with this data; report that as a limitation.

Also report a one-step open-loop "a-prediction" metric distinctly, since closed-loop drift is unforgiving over 60s.

Headline numbers:
- One-step open-loop a RMSE: 0.186 m/s² (median across 30 eval segments)
- Closed-loop v RMSE (60s segments): median 2.23 m/s vs hold-v0 baseline 3.00 m/s
- 17/30 segments beat the trivial baseline; median model/baseline ratio 0.72x

---

## 1. Headline number

**Primary metric**: closed-loop integrated `v` RMSE over full segments (~58 s each, Tesla Model 3, 30 eval segments).

| | Median RMSE (m/s) | Mean RMSE (m/s) |
|---|---|---|
| **Final model** (driver-input only) | **2.23** | 2.87 |
| Baseline: hold v(0) | 3.00 | 4.87 |

Model beats hold-v0 baseline in **17/30 segments** (median ratio model/baseline = **0.72x**).

Secondary metric — open-loop one-step `a` prediction RMSE: **0.186 m/s²** (median across segments). This is the honest "fit quality" number; the v-RMSE is what the integrator costs you.

## 2. What I implemented

- A 5-feature linear acceleration model: `a = β₊·T⁺ + β₋·T⁻ + β_v²·v² + β_v·v + β₀`, where `T` is `di_torque_actual_nm` (drive-inverter torque, sensed from powertrain CAN — NOT measured speed, NOT IMU `a_long`). Splitting `T` into positive (drive) and negative (regen) parts captured asymmetric inverter efficiency.
- Ridge fit (λ=1e-4) against IMU `a_long_mps2` as the regression target, pooled across 20 training segments (`v > 0.5 m/s` mask).
- RK4 closed-loop integrator over `dv/dt = predict_a(v, T)` using only `T(t)` as time-varying input and `v(0)` as initial condition. No measured-speed feedback anywhere in the loop.
- Implied physical coefficients (assuming Tesla M3 mass 2035 kg): drive ≈ 2.6 N/Nm, regen ≈ 3.4 N/Nm, aero `c₂` ≈ 0.99 N/(m/s)², rolling/constant ≈ 546 N. Bearing (linear-in-v) term came out negative (~-33 N/(m/s)) — likely absorbing grade-correlated variance, not a real friction term.

Files:
- `tools/long_model.py`
- `tools/plot_one.py`
- `out/long_model_results.json`
- `out/long_model_example.png`

## 3. How I validated

**Mode**: closed-loop integration over the full segment (~58 s, 2900 samples at 50 Hz). Initial `v` from the segment, then integrate forward using only `di_torque_actual_nm(t)` as input. Reported open-loop one-step `a` RMSE separately as the fit-quality metric.

**Inputs fed to the new model**:
- `di_torque_actual_nm` — **sensed** from powertrain CAN, but commanded by inverter controller; this is the actuator-output signal, not a measurement of the vehicle response.
- `v(0)` — sensed initial speed (the only legitimate measured-state coupling; required to initialise any closed-loop integration).

**Not used**: `v_mps` after t=0, `a_long_mps2` (IMU), wheel speeds, anything driver-pedal-derived (would be cleaner but the model still works).

## 4. Regime breakdown

(closed-loop v RMSE, Tesla)

| Regime (per-sample, by IMU `a`) | Median RMSE (m/s) | n segments |
|---|---|---|
| cruise (|a|<0.3) | 2.27 | 30 |
| accel (a>+0.3) | 2.09 | 28 |
| brake (a<-0.3) | 2.38 | 28 |
| stopped (v<1) | 0.54 | 7 |

The regime split is per-sample within each segment then aggregated — it does not pick clean steady-state segments. Model error is roughly regime-uniform; that's consistent with the drift being dominated by an unmodelled slowly-varying bias (almost certainly road grade), not regime-specific dynamics.

## 5. Surprises

- The naive `hold-v(0)` baseline is surprisingly strong: 3.00 m/s RMSE because the segments don't drift far from their starting speed over 58 s. That sets a high bar — beating it by ~25% is meaningful but not spectacular.
- The implied `β_v` (linear-in-v friction) coefficient came out **negative**. Physically nonsensical for friction — it's almost certainly absorbing the v-correlated portion of the grade signal (cars on highways tend to be on flatter grades when faster; the model learns that). A grade-aware model is the obvious next step.
- The Ford CSVs do not surface `accel_pedal_pct` or `brake_pressed` — those columns are present but identically zero. The Ford adapter clearly didn't decode them (or those signals aren't on the openpilot Ford DBC). That kills "driver-input only" longitudinal modelling on Ford in this dataset.
- Tesla `brake_pedal_state` is also degenerate (constant value 2 across every segment I looked at), so brake torque is unobservable on Tesla too. Lucky that motor torque alone covers regen.

## 6. Limitations

- **Tesla-only**. Could not build the same model for Ford because the only torque/throttle proxy left after the adapter is IMU `a_long`, and using IMU `a_long` to predict `v` is just the original crutch in a different shape.
- **No grade observability**. Road grade is the dominant unmodelled disturbance — a constant 2% grade is ~0.2 m/s², integrated over 60 s = 12 m/s of drift. With only flat-road assumptions the model can't help here. Would want barometric altitude, GPS elevation, or to estimate grade online as a slow random-walk state.
- **No driver-command separation on Tesla brakes**: relying on motor torque alone misses friction-brake events. The `brake_pedal_state` channel decoded by the adapter is degenerate.
- **Fit and eval are different segments but same platform/devices**. Did not split by device/route, so train and eval segments may share calibration biases.
- **Single fixed train/eval split** (first 20 vs next 30 segments by filename order). No cross-validation due to time budget.
- **What I'd want next**: (a) grade estimator co-fitted with the longitudinal coefficients; (b) Ford pedal decoding; (c) per-device/route held-out validation; (d) compare against simply integrating IMU `a_long` to quantify how much extra error the driver-input formulation costs over an IMU-fed integrator; (e) hybrid model that resets v from measurement at low-confidence intervals.

## Harness notes

- Did not encounter the `Write` block on report-style filenames; only wrote Python under `tools/`, JSON+PNG under `out/`.

```
ISOLATION_REPORT:
read_outside_allowed: []
attempted_blocked: []
shared_dir_writes: []
notes: "Built a Tesla-only longitudinal model from drive-inverter torque (sensed actuator-side, not measured speed). Ford CSVs have all-zero accel_pedal_pct and brake_pressed columns so the same exercise wasn't possible on Ford without falling back to IMU a_long, which would just relocate the crutch."
```
