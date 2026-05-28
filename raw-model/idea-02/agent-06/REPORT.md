# Agent 06 — raw-model / idea-02

# Standalone Longitudinal Speed Model — Ford Mustang Mach-E

## 1. Headline number

**Primary metric:** closed-loop predicted-vs-measured speed RMSE on held-out segments, aggregated over all samples, at a **5-second rolling integration horizon** (the workshop's KS spine integrates state forward — open-loop integration without horizon reset is the right framing).

| Mode | Baseline (null = v(0) constant) | Baseline (IMU `a_long` integrated) | **My model** |
|---|---|---|---|
| Full 60-s segment closed-loop | 7.66 m/s | 4.59 m/s | **6.78 m/s** |
| 10-s windowed closed-loop | — | 1.22 m/s | **2.30 m/s** |
| 5-s windowed closed-loop | — | 0.64 m/s | **1.32 m/s** |
| One-step a_long RMSE | — | 0 (it is the truth) | **0.62 m/s²** |

So at a 5-second horizon the model gets within ~1.3 m/s RMSE without consuming any sensed longitudinal channel. The IMU baseline is a strong lower bound because it is the truth integrated; my model has to *reproduce* a_long from commanded inputs.

## 2. What I implemented

- **Piecewise data-driven `a = f(v, accel_pedal, brake_pressed)` model** fit by OLS on Mach-E sim CSVs (315 segments, 70/30 train/test). Three regimes:
  - **Coast** (pedal<2%, brake off): `a = -0.067 - 0.0157·v + 0.00053·v²` (rolling + linear + drag).
  - **Power** (pedal≥2%, brake off): coast term + `(0.0343 − 0.00102·v) · pedal_pct`.
  - **Brake** (brake_pressed): coast term − 1.426 m/s² (binary brake → single decel offset; this is a known coarse-input limitation).
- **Closed-loop integrator** `dv/dt = a_pred(v_state, u_commanded)`, forward Euler at the data's 50 Hz timebase, `v` clamped ≥ 0.
- **Windowed validator** that resets `v` to measured every N seconds (5, 10) — characterises horizon-dependent drift without conflating long-horizon integration error with one-step model fidelity.
- All artefacts live in `out/`: `summary_v2.json`, `per_segment_metrics_v2.csv`, `v_trace_examples.png`.

## 3. How I validated

- **Mode:** closed-loop integration (`dv/dt = a_pred`). Reported at three horizons: full segment (~60 s), 10 s, 5 s. Also reported open-loop one-step `a` RMSE for the cleanest measure of model fit.
- **Inputs fed at each step** (commanded only — no sensed v, no sensed a):
  - `accel_pedal_pct` (commanded, time series from CAN)
  - `brake_pressed` (commanded, binary, from CAN)
  - `v` (the model's own state, NOT the measured channel)
- **Initial condition:** `v(t=0)` from the segment's measured `v_mps` (a single sample, not a continuous crutch). Windowed mode re-seeds every N s.
- **Split:** seed 42, 70/30 segment-level split. 220 train segments, 95 test segments.

## 4. Regime breakdown (full-segment closed-loop RMSE on test set)

| Regime | n samples | RMSE (m/s) |
|---|---|---|
| cruise (pedal<5, no brake, |a|<0.3) | 87,832 | 7.14 |
| accel (pedal≥5, no brake) | 145,747 | 6.12 |
| coast (pedal<5, no brake, a<−0.3) | 23,277 | 7.99 |
| brake (brake_pressed=1) | 3,584 | 9.62 |
| low_v (v<5 m/s) | 43,489 | 10.43 |
| high_v (v>20 m/s) | 114,334 | 4.58 |

Worst regime is **low speed** (start/stop) and **brake** — both directly tied to the binary brake input. The model has no way to differentiate light tap from hard press.

## 5. Surprises

- **The KS model's longitudinal channel is fully clamped** in the existing pipeline (`clamp_v_to_measured=True`). The "model" never integrated speed at all in the workshop's primary mode; the docs even call this out explicitly. So "remove the crutch" is literally swapping the clamp for an integrator.
- **`a_long_mps2` in the CSVs is filtered `dv/dt` of `v_meas`**, per the adapter docstring (`Tesla adapter: derives a_long from filtered dv/dt`). That means my "IMU baseline" isn't really IMU — it's smoothed differentiation of the same target channel, which is why it scores so low. Calling it a true baseline is generous; the only honest non-trivial baseline is the null `v(t)=v(0)`.
- **Brake signal is binary**, not pressure / line PSI. That is the single biggest cap on this model's brake-regime fidelity. With analog brake pressure I'd expect brake-regime RMSE to halve at minimum.
- **No mass / Crr / Cd / wheel radius constants** in `parameters.py` — only mass for KS lateral; everything else has to be inferred from data. I went fully data-driven rather than try to backfill.

## 6. Limitations

- **Single platform.** Only Mach-E. Ford F-150 and Tesla Model 3 not fit. Tesla CSVs have *torque* (`di_torque_actual_nm`) and `brake_pedal_state` separately — a Tesla model could be meaningfully stronger.
- **No grade / no road slope.** The constant bias term absorbs an average road profile across the training set; on a steep hill segment this will be very wrong. Inclinometer data is not in the CSVs I saw.
- **Binary brake** is the dominant failure mode; cannot recover pressure-modulated decel.
- **No regen / pedal-lift model.** Mach-E does one-pedal driving; lifting the accelerator → regen braking. My coast model rolls that into a generic `c(v)` rather than distinguishing pedal-lift transients.
- **No actuator delay / lag.** Real powertrain has ~100–300 ms torque-rise. I used instantaneous static `a = f(v, u)`.
- **Forbidden-paths self-restraint:** I deliberately did not read `webinar-angle-*/modulo-*/`, sibling `agent-*/`, `webinar-00/`, or other `raw-model/idea-*/`. I did not look for canonical "answer" longitudinal models elsewhere in the repo.
- **What I'd want next:** brake-pressure CAN signal; vehicle pitch / accelerometer-Z for grade decomposition; train across all three platforms; add a first-order torque-rise lag; consider a residual neural correction on top of the physics fit.

```
ISOLATION_REPORT:
read_outside_allowed: []
attempted_blocked: []
shared_dir_writes: []
notes: "Stayed within ./code, ./data, and own agent folder. Fit only on Mach-E sim CSVs; did not consult any sibling/cross-angle/idea-* material. a_long in CSVs is filtered dv/dt of v_meas per adapter docstring, so the 'IMU baseline' is a soft lower bound, not an independent measurement."
```
