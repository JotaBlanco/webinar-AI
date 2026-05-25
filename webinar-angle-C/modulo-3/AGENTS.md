# AGENTS.md — módulo 2

> **The ratchet substrate.** Every line below was added because a previous run of the bare harness (módulo 1) made the mistake the line prevents. Nothing here is speculative. If you find a *new* recurring mistake while solving the challenge, add it here — that is the discipline being demonstrated.

## Project purpose

Compare a Kinematic Single-Track (KS) vehicle dynamics model's predictions against real CAN-bus measurements (Ford openpilot rlogs). The thing under test is the **residual** between predicted and measured lateral channels (`yaw_rate`, `a_y`). Speed-known lateral-only mode is the operating contract.

## Build / run

- Python 3.11+. Use the repo `.venv` if present.
- Outputs go in `out/` inside this module. **Never** write to `data/` and **never** edit `code/` in place — both are shared with the other modules running in parallel.

## Vehicle dynamics — units and sign conventions

Every line here was added after an agent confused one of these. Do not skip.

- **Coordinate frame is ISO 8855.** X forward, Y to the **left**, Z up. A left turn produces a **positive** yaw rate. If you ever introduce a sign flip, justify it in writing.
- **Steering wheel angle vs road wheel angle.** Steering wheel = degrees, on CAN. Road wheel = radians, for the model. Conversion: `delta_road_rad = delta_wheel_deg / steering_ratio / (180/π)`. Use `delta_road_rad` for the model; never feed raw degrees to a radian-expecting integrator.
- **Yaw rate units.** Column `yaw_rate_meas_rads` and `yaw_rate_pred_rads` are **rad/s**, *not* rad. The suffix `_rads` means "rad per second". Convert to °/s for reporting: `* 180 / π`.
- **Residual sign convention.** `resid = meas − pred`. Always. A positive yaw-rate residual means the car turned more than the model predicted.
- **SI for modelling.** Angles in radians, speed in m/s, acceleration in m/s², distance in metres. Steering wheel angle in degrees is the only allowed exception (CAN-native unit).

## Operating contract — speed-known lateral-only

- Calls to `simulate_ks` must use `clamp_v_to_measured=True` *and* `clamp_delta_to_measured=True` for real-data runs. The integrator still computes `dv/dt` and `dδ/dt` internally, but the results are overwritten by the measured values every step.
- The longitudinal channel is **input**, not output. Do not report longitudinal RMSE as a model-fidelity number; by construction it's zero modulo numerical noise.
- The lateral channel (`ψ`, `ψ̇`, `a_y`, `x`, `y`) is what gets predicted. The Ford CSVs contain measured `yaw_rate_meas_rads` and `a_lat_meas_mps2` as truth. Use the CSV's pre-computed `*_resid_*` columns rather than recomputing — they have the right sign convention.

## Data and code — what's where

- `data/raw/segments/<PLATFORM>/<device>/<route>/<idx>/rlog.zst` — input.
- `data/sim/segments/<PLATFORM>/<device>/<route>/<idx>/sim.csv` — already-generated outputs (read-only for you).
- `code/_README.md` — full description of what each script does. Read it before running anything you don't recognise.
- Only Ford CSVs (`FORD_MUSTANG_MACH_E_MK1`, `FORD_F_150_LIGHTNING_MK1`) carry truth channels. Tesla CSVs don't — don't try to compute yaw-rate residuals on Tesla.

## Known traps (every entry = a past agent failure)

- An agent once resampled CAN signals at 100 Hz and the steering signal aliased. The adapter defaults to 50 Hz. Don't change it without a reason.
- `a_long_mps2` from CAN is not a clean longitudinal acceleration — it carries grade + powertrain transients + sensor bias. The low-passed version at 5 Hz inside the adapter is the one to use for model input.
- The KS model assumes wheels point in the direction the car goes. At any meaningful speed/lateral-G that's false (slip angle non-zero). **That is the whole point of this challenge.** Quantify the residual; do not pretend the model is wrong because of a bug.
- Don't bump `code/_schema/` pins (capnp / DBC). The input contract assumes them.
- Don't trust GPS heading below ~3 m/s. Use IMU-integrated heading instead.
- Tesla's IMU yaw-rate channel isn't decoded yet. Tesla CSVs have predictions but no truth — your challenge is Ford-only.

## How to extend the model (without breaking anything else)

- Copy the relevant file from `code/` (typically `ks_model.py`, `generate_simdata_ford.py`, or `parameters.py`) into `out/` or a subdir, modify, run from there.
- Do not edit `code/parameters.py` in place — values are openpilot-canonical, sourced from the rlog `carParams`. If you re-calibrate, document baseline-vs-fitted in your `REPORT.md`.

## Workflow — RPI loop (Planning component, 4)

Non-trivial work follows Research → Plan → Implement across three artifacts: `rpi/runs/<timestamp>/{research,plan,implement-notes}.md`. The plan is locked before implementation. See [`rpi/RPI_INSTRUCTIONS.md`](rpi/RPI_INSTRUCTIONS.md). Templates in [`rpi/templates/`](rpi/templates/).

## Evals (Verification component, 5)

- `evals/schema_check.py` — computational sensor over every CSV your variant produces. Failing variants do not enter the ablation.
- `evals/baseline_rmse.py` — reproducible baseline numbers; your REPORT.md must match these within rounding.
- `evals/consistency_judge.md` — inferential sensor spec (LLM-as-judge over the final REPORT.md). Run last, by the facilitator.
- Rule of thumb: **computational first; inferential only where it earns it.**

## Skills inventory

*(None in this module.)* The Modularity component (6) is added in module 4.
