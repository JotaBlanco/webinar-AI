# Project notes — sim-real runtime

> Raw braindump from the engineer who set up this workspace. Has not been refactored. Read it once and try to figure out the rest from the code itself.

This workspace holds the data and code half of a sim-real correlation effort. There is a Kinematic Single-Track (KS) model that predicts lateral vehicle dynamics from real CAN-bus inputs captured by openpilot, on three platforms. Ford CSVs contain a measured yaw-rate and lateral-G truth channel; Tesla CSVs don't.

## Layout

```
<your-module>/
  code -> ../../code           # symlink (read-only by convention)
  data -> ../../data           # symlink (read-only by convention)
  tools/                       # tiny wrappers around `code/` you can use
  tasks/challenge.md           # your job
  out/                         # everything you produce goes here
```

```
data/
  raw/segments/<PLATFORM>/<device>/<route>/<idx>/rlog.zst   # input
  sim/segments/<PLATFORM>/<device>/<route>/<idx>/sim.csv    # already-generated outputs from generate_simdata*.py
```

Platforms present under `data/raw/segments/` and `data/sim/segments/`:

- `TESLA_MODEL_3`
- `FORD_MUSTANG_MACH_E_MK1`
- `FORD_F_150_LIGHTNING_MK1`

## How to run

System `python3` already has `pandas`, `numpy`, `scipy`, `matplotlib` pre-installed. Run scripts as `python3 ...`.

```bash
python code/run_ks_synthetic.py            # synthetic open-loop demo
python code/generate_simdata_ford.py       # rlog → KS → CSVs (Ford only has truth channels)
python code/plot_simdata_ford.py           # PNGs alongside CSVs
```

`code/_README.md` has a longer description if you want it.

## What the model does

It's a kinematic single-track model. Real-data runs are in "speed-known lateral-only" mode — `clamp_v_to_measured=True` and `clamp_delta_to_measured=True`, so the integrator clamps `v` and `δ` to measured values at every step and only the lateral states (yaw, yaw-rate, a_y, x, y) are predicted. That's the operating contract for this workspace.

## CSV columns (Ford only — Tesla doesn't have the truth channels)

The per-segment CSVs at 50 Hz include columns like:

- `t_s`, `delta_wheel_deg`, `delta_road_rad`, `v_mps`, `a_long_mps2`
- `a_lat_meas_mps2`, `yaw_rate_meas_rads`  ← measured truth (Ford only)
- `x_m`, `y_m`, `psi_rad`, `v_state_mps`, `delta_state_rad`
- `yaw_rate_pred_rads`, `a_y_pred_mps2`  ← KS prediction
- `yaw_rate_resid_rads`, `a_y_resid_mps2`  ← `meas - pred`

If a column you need isn't here, `head` one of the CSVs.

## Misc

- `_schema/` under code/ holds pinned cereal/DBC schemas. Don't bump them.
- `tools/` in your module is bare — feel free to add helpers.
- Outputs (new CSVs, plots, reports) go in `out/` inside your module, never in `data/sim/`.
