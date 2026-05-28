# CLAUDE.md — workspace notes

> Engineer's working notes about the workspace itself — separate from AGENTS.md (which is the project conventions). Both files are loaded into context on every turn so the agent has full visibility into the workspace shape and the team conventions at all times.

## Where things live (canonical paths)

This workspace is one module of a larger workshop run. Inside your module folder you have:

```
<your-module>/
  AGENTS.md                ← team conventions, sign rules, fidelity ladder, traps
  CLAUDE.md                ← this file — workspace layout + how to run things
  code -> ../../../code    ← symlink to the shared codebase, read-only by contract
  data -> ../../../data    ← symlink to the shared dataset, read-only by contract
  tasks/                   ← your job description for this run
  tools/                   ← thin wrappers you can write
  out/                     ← everything you produce (scripts, plots, CSVs, REPORT.md)
```

The shared `code/` directory (resolved through the symlink) contains:

```
code/
  _README.md                       ← longer description; read if you want
  _schema/                          ← pinned cereal/DBC schemas — don't bump them
  __pycache__/
  ks_model.py                       ← the kinematic single-track model — `simulate_ks(...)`
  parameters.py                     ← PARAM_BY_PLATFORM dict — look up everything from here
  adapter_ford_rlog.py              ← Ford CAN decoder (DBC: opendbc/ford_lincoln_base_pt)
  adapter_tesla_rlog.py             ← Tesla DBC adapter (no IMU truth)
  build_manifest.py                 ← walks data/raw/segments to build the segment manifest
  fetch_ford_f_150_lightning_mk1.py ← downloader (you don't need this — segments already on disk)
  fetch_ford_mustang_mach_e_mk1.py  ← downloader
  fetch_tesla_model_3.py            ← downloader
  fetch_tesla_model_3.log           ← log of the last Tesla fetch run
  generate_simdata.py               ← Tesla rlog → KS → sim CSVs
  generate_simdata_ford.py          ← Both Fords rlog → KS → sim CSVs (the script that produced your data)
  inspect_rlog.py                   ← interactive rlog viewer
  plot_simdata.py                   ← Tesla sim CSV plotter
  plot_simdata_ford.py              ← Ford sim CSV plotter — PNGs alongside CSVs
  rlog_reader.py                    ← capnp rlog decoder
  run_ks_synthetic.py               ← synthetic open-loop KS demo (no rlog needed)
  synthetic_inputs.py               ← canned synthetic input shapes for testing
  viz_compare_jupyter.ipynb         ← notebook for sim-real comparison
  viz_compare_matplotlib.py         ← non-notebook matplotlib comparison
  viz_compare_plotly.py             ← plotly variant
  viz_compare_rerun.py              ← rerun.io variant
```

The shared `data/` directory contains:

```
data/
  raw/segments/<PLATFORM>/<device>/<route>/<idx>/rlog.zst
  sim/segments/<PLATFORM>/<device>/<route>/<idx>/sim.csv
```

Platforms present:

- `TESLA_MODEL_3` — 1025 raw segments, 1.785 GB. The Tesla third-party DBC does not decode the IMU, so Tesla CSVs have **no measured truth yaw rate**. Lateral fidelity scoring on Tesla is not possible today; do not use Tesla for this challenge.
- `FORD_MUSTANG_MACH_E_MK1` — 315 raw segments, 0.817 GB. Ford CSVs **do** have decoded measured truth (`yaw_rate_meas_rads`, `a_lat_meas_mps2`).
- `FORD_F_150_LIGHTNING_MK1` — 230 raw segments, 0.597 GB. Same as Mach-E — truth channels available.

The pre-generated sim CSVs are under `data/sim/segments/<PLATFORM>/<device>/<route>/<idx>/sim.csv`. Each Ford CSV has 18 columns at 50 Hz; the canonical column list is in AGENTS.md. You should not need to regenerate the CSVs — the simulator runs have already been done; your job is to analyse the residuals and propose model improvements.

## How to run things (commands you may want)

```bash
# These are example commands the engineering team uses. You should not need to run any of these for the residual-analysis task, but they are here for completeness.

python3 code/run_ks_synthetic.py            # synthetic open-loop demo, no rlog needed
python3 code/generate_simdata.py            # Tesla rlog → KS → data/sim/ (would overwrite — DON'T)
python3 code/generate_simdata_ford.py       # both Fords (would overwrite — DON'T)
python3 code/generate_simdata_ford.py FORD_MUSTANG_MACH_E_MK1
python3 code/plot_simdata_ford.py           # PNGs alongside CSVs

# What you probably want to do for this task:
python3 -c "import pandas as pd; df = pd.read_csv('data/sim/segments/FORD_MUSTANG_MACH_E_MK1/.../sim.csv'); print(df.head())"
```

## What the project is, in a sentence

This is a sim-real correlation runtime around the **CommonRoad kinematic single-track (KS)** vehicle dynamics model. It runs the KS model on real openpilot rlog driving data and compares predicted lateral state (yaw rate `ψ̇`, lateral acceleration `a_y`) against the measured truth channels. The team wants the lateral predictions to be better. **That is your job.**

It is **not** a longitudinal-fidelity sandbox. Speed and steering angle are clamped to the measured values at every integration step (see AGENTS.md operating contract section). Reporting speed-vs-measured RMSE is meaningless; we know it's zero by construction.

## Operating contract — repeated here for emphasis

Real-data KS runs in this workspace operate with:

```python
simulate_ks(..., clamp_v_to_measured=True, clamp_delta_to_measured=True)
```

This means `v` and `δ` are inputs, not outputs. The integrator's own updates to these states are overwritten by the measurement at every step. The predicted channels are `yaw_rate_pred_rads` and `a_y_pred_mps2`. The measured truth channels (Ford only) are `yaw_rate_meas_rads` and `a_lat_meas_mps2`. The residual under test, already pre-computed in the CSV, is:

```
yaw_rate_resid_rads = yaw_rate_pred_rads - yaw_rate_meas_rads
```

## A few more things worth knowing about the workspace

- The `code/_schema/` directory holds pinned `cereal.capnp` and DBC schemas. These match the openpilot version that produced the rlogs. **Don't bump them** — any change would invalidate the existing rlogs.
- The `tools/` directory inside your module is bare. You're welcome to add helpers there for your own use.
- Outputs (new CSVs you generate, plots, the report) go in `out/` inside your module — never in `data/sim/`. The shared dirs are read-only by contract.
- If you need to read an rlog directly (you shouldn't for this task — the sim CSVs already exist), the dependency `pycapnp` and `cantools` may or may not be installed; check before assuming.
- The team's preferred plot style is matplotlib with `tight_layout` and a 1:1 aspect ratio for trajectory plots. PNGs are fine; SVGs are over-engineering for a quick diagnosis.

## A note about the sub-agent harness

The harness you run inside blocks `Write` on filenames matching `(report|findings|summary|analysis).*\.md$`. You will not be able to write `REPORT.md` directly. Return the report content in your final response and the orchestrator will persist it. This is unrelated to the task itself, but it has bitten every agent that has worked here so far, so be aware.
