---
name: sim-real-runtime
description: Operational layout of the workspace (data tree, code tree), CSV schema, the speed-known lateral-only operating contract, and how to run the sim generators end to end. Load when running code, reading data for the first time in a session, or interpreting the CSV columns.
when-to-invoke: User asks to run scripts, regenerate sim data, locate a file, or read a CSV column. Not needed if you already know where things are.
load-cost: ~55 tokens metadata, ~600 tokens body.
---

# sim-real-runtime

## Workspace layout

```
<workspace>/
  AGENTS.md, skills/, references/, tasks/   ← substrate (this layer)
  code/    → symlink to the shared code tree (read-only by convention)
  data/    → symlink to the shared data tree
    raw/segments/<PLATFORM>/<device>/<route>/<idx>/rlog.zst
    sim/segments/<PLATFORM>/<device>/<route>/<idx>/sim.csv
```

Three platforms in `data/raw/segments/` and `data/sim/segments/`:

- `TESLA_MODEL_3` — Tesla party DBC. KS prediction only; no measured yaw-rate truth (IMU not decoded).
- `FORD_MUSTANG_MACH_E_MK1` — openpilot ford_lincoln_base_pt DBC. Prediction + truth.
- `FORD_F_150_LIGHTNING_MK1` — same DBC. Prediction + truth.

The lateral-fidelity workflow uses the two Ford platforms only.

## Operating contract: speed-known lateral-only

`simulate_ks(..., clamp_v_to_measured=True, clamp_delta_to_measured=True)`. The integrator still runs `dv/dt = a` and `dδ/dt = δ̇` internally, but their results are overwritten by the measured values at every step.

Implications:
- The model's longitudinal channel is an **input**, not an output. Reporting "longitudinal residual" is meaningless under this contract.
- The model's lateral channel — yaw rate, lateral acceleration, heading, planar trajectory — is what gets predicted. The Ford CSVs include the measured yaw rate and lateral acceleration alongside the prediction so the residual is computable directly.
- `KSDriverInputs.a` and `KSDriverInputs.delta_dot` are still populated (from the IMU and from `gradient(δ_meas)` respectively), but the integrator ignores them under the clamps. They live in the CSV for side-panel analyses.

To run open-loop instead (no clamping), set both flags to `False`. The synthetic demo `run_ks_synthetic.py` already uses that mode.

## How to run

```bash
# regenerate all Ford sim CSVs (default: 2 segments per Ford platform)
python code/generate_simdata_ford.py

# Mach-E only / F-150 only
python code/generate_simdata_ford.py FORD_MUSTANG_MACH_E_MK1
python code/generate_simdata_ford.py FORD_F_150_LIGHTNING_MK1

# render comparison PNGs (one per segment)
python code/plot_simdata_ford.py
```

Scripts resolve paths via `Path(__file__).resolve().parents[1]` — they work correctly under the symlink layout because `Path.resolve()` follows it.

## Sim CSV schema (one row per 50 Hz sample)

```
t_s
delta_wheel_deg, delta_road_rad, v_mps, a_long_mps2
a_lat_meas_mps2, yaw_rate_meas_rads        # TRUTH (Ford only)
accel_pedal_pct, brake_pressed
x_m, y_m, psi_rad, v_state_mps, delta_state_rad
yaw_rate_pred_rads, a_y_pred_mps2
yaw_rate_resid_rads, a_y_resid_mps2        # measured − predicted
```

`yaw_rate_resid_rads` and `a_y_resid_mps2` are pre-computed at generation time. RMSE on `yaw_rate_resid_rads` (converted to °/s for reporting) is the canonical model-fidelity number for the workshop.

## Files in code/ worth knowing

- `ks_model.py` — `KSState`, `KSDriverInputs`, `KSTrajectory`, `ks_dynamics(state, u, p)`, `rk4_step(...)`, `simulate_ks(...)`.
- `parameters.py` — dataclasses per platform: `MachEKS` / `MachEST`, `F150LightningKS` / `F150LightningST`. `PARAM_BY_PLATFORM` for keyed lookup. ST dataclasses already include m, I_z, l_f, l_r, C_alpha_f, C_alpha_r, i_s.
- `adapter_ford_rlog.py` — `load_segment_measurements(rlog_path, steer_ratio, sample_rate_hz)` → resampled measurement struct (`t`, `delta_wheel_deg`, `delta_road_rad`, `v_mps`, `a_long_mps2`, `a_lat_mps2`, `yaw_rate_rads`, …).
- `generate_simdata_ford.py` — driver script: pick segments, decode, clamp-and-integrate, write CSV + manifest.

## Things that have broken before

- Resampling at 100 Hz aliased the steering signal. Use the adapter's 50 Hz default.
- Pinned schema commits in `code/_schema/cereal/COMMIT.txt` and `code/_schema/dbc/COMMIT.txt` — don't bump unless you know what you're doing.
- Tesla side has no yaw-rate truth; Tesla CSVs' `yaw_rate_meas_rads` column does not exist. Only Ford.
