---
name: vehicle-dynamics-rlog
description: Conventions for interpreting CAN/IMU signals from openpilot rlogs in the sim-real workflow — units, sign rules (ISO 8855), the model fidelity ladder (KS / ST / non-linear tyre), and the gotchas a vehicle-dynamics engineer takes for granted. Load before interpreting a yaw-rate or lateral-G signal, or before modifying the model.
when-to-invoke: User asks to interpret raw CAN signals, compare predicted vs measured, modify the KS/ST model, propose a new lateral fidelity improvement, or analyse a sim residual. Not needed for pure data plumbing.
load-cost: ~60 tokens metadata, ~700 tokens body.
---

# vehicle-dynamics-rlog

## Coordinate frame: ISO 8855

The vehicle body frame uses **ISO 8855**: X forward, **Y left**, Z up. Yaw (ψ) is positive counterclockwise viewed from above — i.e. **a left turn produces positive yaw rate and positive lateral acceleration** in the body frame. This is the convention used by the model code (`code/ks_model.py`) and by the Ford CAN signals as decoded by `code/adapter_ford_rlog.py`. Both sides agree out of the box — do not reintroduce a sign flip.

Common confusion: SAE J670 has Y right and Z down. Aerospace NED is X north / Y east / Z down. If a third-party tool uses either, convert to ISO 8855 *before* feeding the model.

## Units (modelling vs reporting)

Inside the model: every angle in **radians**, speed in **m/s**, acceleration in **m/s²**, distance in **m**, time in **s**, cornering stiffness in **N/rad**.

Two exceptions in reporting (because they're how the CAN bus or the workshop reports them):
- Steering wheel angle in **degrees** at the CAN signal level (`delta_wheel_deg`); the road-wheel angle (`delta_road_rad`) is the radians-divided-by-steering-ratio version that the model consumes.
- RMS of yaw-rate residuals reported in **°/s** (more readable than rad/s); the code converts at the report step.

## Fidelity ladder

- **KS — Kinematic Single-Track.** What `code/ks_model.py` implements. Driving-school model: rigid rod of wheelbase L, no tyre, no slip, `ψ̇ = (v/L)·tan(δ)`. The lie this tells: at any meaningful speed and lateral G, slip angle is non-zero, so the measured `ψ̇` is smaller than the KS prediction (the tyres "give"). This is the *headline* lateral residual the workshop sets out to quantify.
- **ST — Single-Track Dynamic.** Adds lateral force balance with linear tyre cornering stiffnesses C_α,f / C_α,r. ST parameters for all three platforms are already in `code/parameters.py` (`MachEST`, `F150LightningST`, etc.) — wheelbase split (l_f, l_r), mass m, yaw inertia I_z, cornering stiffnesses. `code/ks_model.py` does **not** implement ST yet; an `st_model.py` would need to be authored. The ST states add `β` (sideslip angle) and `ψ̇` becomes a true integrated state (not a derived output).
- **Non-linear tyre (Pacejka magic formula).** Captures saturation in high-G regimes (|a_y| > ~4 m/s²). Out of default scope unless the residual clearly demands it.
- **Full multi-body (CarSim/Adams).** Out of scope for the workshop.

## What the residual is telling you

`yaw_rate_resid = yaw_rate_meas - yaw_rate_pred`. Signed and time-resolved. Some patterns to look for:

- **Sign-correlated bias** (resid same sign as ψ̇_meas): the model is over-predicting turn rate. The classic KS-vs-ST gap — KS ignores tyre lateral compliance, so it turns the car too aggressively for a given δ. **Expected** under default KS. Magnitude grows with |a_y| and with v.
- **Lag** (resid leads or trails the input): steering compliance, sensor latency, or a missing filter in the adapter chain. Cross-correlate `δ_meas` and `ψ̇_meas` to bound it.
- **Constant offset** (resid mean ≠ 0 even at |ψ̇| ≈ 0): yaw-rate sensor bias or a sign convention mismatch. Check on straight-line driving sections (small |δ| AND small |ψ̇_meas|).
- **Regime-dependent gain** (resid/ψ̇_meas changes with v or |a_y|): non-linear tyre, weight transfer, or speed-dependent steering compliance. Worth segmenting the residual by speed bins and lateral-G bins.

## Standard signal gotchas

- **GPS heading at low speed** is noisy below ~3 m/s — don't use it as ground truth at parking-lot pace.
- **`a_long_mps2` from CAN** carries grade + powertrain + bias on top of true longitudinal accel. Adapters low-pass it at 5 Hz; treat the long-channel as auxiliary, not truth.
- **Tesla rlogs have no decoded yaw-rate truth channel** (the Tesla party DBC exposes the QF bits but not the values). Only Ford CSVs carry `yaw_rate_meas_rads`. Don't propose Tesla-side residual work.
- **Wheel-speed-vs-IMU-speed mismatch**: wheel speed is overestimated on slipping wheels (regen on EVs, light traction loss). `v_mps` in the CSV is wheel-derived; for high-precision work, prefer IMU-integrated v.

## Naming conventions in this project

Lowercase + underscores. Greek letters spelled out (delta, psi, beta). Suffixes: `_rad` (angle), `_rads` (rad/s — note plural is rate not radians), `_mps` (m/s), `_mps2` (m/s²), `_deg` (degrees), `_meas` (measured), `_pred` (predicted), `_resid` (= meas − pred).
