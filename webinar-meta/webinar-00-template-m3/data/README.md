# data

Sim data tree for the lateral-fidelity task. Read-only. Symlinked into this template from the project's top-level `data/` directory — `git status` should not show changes here.

## Expected layout

```
data/
├── raw/         (raw rlogs — adapter source)
├── sim-only/    (input-only mirror — what your predict() sees at scoring time)
│   └── <PLATFORM>/<DEVICE>/<ROUTE>/<IDX>/
│       └── sim.csv     ← 8 columns: t_s, delta_*, v_mps, a_long_mps2,
│                          accel_pedal_pct, brake_pressed, yaw_rate_pred_rads
└── sim-full/    (full schema including truth — for scoring & training)
    └── <PLATFORM>/<DEVICE>/<ROUTE>/<IDX>/
        └── sim.csv     ← above + yaw_rate_meas_rads, a_lat_meas_mps2,
                          residuals, simulator state
```

## The operating contract

`sim-only/` is the **agent-facing view of the input** — what the canonical grader hands to your `predict()`. The truth channel (`yaw_rate_meas_rads`) and its kinematic shadow (`a_lat_meas_mps2`) literally don't exist in these files. If your predict tries to read them, you get a `KeyError`.

`sim-full/` is for **scoring & training tooling only** — the local `score-model/` skill reads truth from here, strips inputs to the allowlist, then calls your predict. Same dual-file pattern as the canonical grader. Your local RMSE will match the canonical RMSE.

Every skill in `skills/` that touches data assumes the `<PLATFORM>/<DEVICE>/<ROUTE>/<IDX>/sim.csv` shape. Platform is the 3rd-from-rightmost directory; route is the 2nd-from-rightmost.

## Setup

If this directory is empty when you clone the template, create the symlinks:

```bash
ln -s /path/to/project/data/raw data/raw
ln -s /path/to/project/data/sim-only data/sim-only       # input-only mirror
ln -s /path/to/project/data/sim/segments data/sim-full   # full schema with truth
```
