# CLAUDE.md — Project Notes (dump)

> This file was added after the team's first agent run failed. The engineer's first instinct was: "the agent needs more context." So they dumped everything they could think of here. It is now read on every turn alongside AGENTS.md. The team has not yet refactored this content — it sits as a raw braindump.

## Project layout (raw notes)

The data and code in this workspace are the *runtime* half of a sim-real correlation workshop. The *design* half lives in a sister knowledge base (not accessible here) that contains workshop ideas, dream-team notes, simulation-tool comparisons, and per-vehicle parameter writeups. If you are here you are in the runtime; you cannot reach the design notes.

```
<workspace>/
  data/
    raw/segments/<PLATFORM>/<device>/<route>/<idx>/rlog.zst   ← downloaded by code/fetch_*.py
    sim/segments/<PLATFORM>/<device>/<route>/<idx>/sim.csv    ← produced by code/generate_simdata*.py
  code/                                                        ← all Python, flat (see code/_README.md)
```

Three platforms currently present under both `data/raw/segments/` and `data/sim/segments/`:

- `TESLA_MODEL_3` — 1.785 GB raw / 1025 segments. Tesla party DBC decode. Lateral KS prediction only; measured yaw-rate truth channel not yet decoded.
- `FORD_MUSTANG_MACH_E_MK1` — 0.817 GB raw / 315 segments. openpilot ford_lincoln_base_pt DBC. Both KS prediction *and* measured yaw-rate + lateral-G truth in the CSV.
- `FORD_F_150_LIGHTNING_MK1` — 0.597 GB raw / 230 segments. Same DBC. Same prediction-vs-truth structure.

## Operating contract (raw notes)

Real-data runs operate in **speed-known lateral-only** mode: measured `v` and measured `δ` are clamped at every integration step, so the KS model predicts only the lateral subset `(ψ, ψ̇, a_y, x, y)`. The longitudinal channel is input, not output. Full rationale is in the design KB (not accessible here). The mechanical short version: `simulate_ks` is called with `clamp_v_to_measured=True` *and* `clamp_delta_to_measured=True`. The integrator still runs `dv/dt = a` and `dδ/dt = δ̇` internally, but their results are overwritten by the measured values at every step.

`KSDriverInputs.a` and `KSDriverInputs.delta_dot` are still populated (from the IMU and from `gradient(δ_meas)` respectively), but the integrator ignores them under the clamps. They live in the CSV for side-panel analyses.

## How to run things (raw notes)

```bash
# from any working directory that contains the code/ and data/ symlinks
python code/run_ks_synthetic.py             # synthetic open-loop, no rlog needed
python code/generate_simdata.py             # Tesla rlog → KS → data/sim/
python code/generate_simdata_ford.py        # Mach-E + F-150 rlog → KS → data/sim/
python code/plot_simdata_ford.py            # render PNGs from sim CSVs
```

The cereal capnp schema (from `commaai/openpilot`) and the Tesla party DBC (from `commaai/opendbc`) are pinned in `code/_schema/` — committed at the SHAs in `code/_schema/cereal/COMMIT.txt` and `code/_schema/dbc/COMMIT.txt`. Don't bump them unless you know what you're doing — the workshop input contract assumes the pinned schema.

## CSV columns (raw notes)

Per-segment CSVs at 50 Hz with these columns (one header row, all floats):

```
t_s
delta_wheel_deg, delta_road_rad, v_mps, a_long_mps2
a_lat_meas_mps2, yaw_rate_meas_rads          # TRUTH (Ford only)
accel_pedal_pct, brake_pressed
x_m, y_m, psi_rad, v_state_mps, delta_state_rad
yaw_rate_pred_rads, a_y_pred_mps2
yaw_rate_resid_rads, a_y_resid_mps2          # measured − predicted
```

The residual columns are the workshop's payload. RMSE on `yaw_rate_resid_rads` is the canonical model-fidelity number.

## Things that have broken before (raw notes)

- Someone resampled CAN signals at 100 Hz once and the steering signal aliased — use the adapter's default of 50 Hz unless you have a reason otherwise.
- Don't trust `a_long_mps2` from CAN as a clean reading of longitudinal acceleration; it carries grade + powertrain transients + sensor bias. The low-passed version at 5 Hz is the one used by the adapter.
- The Tesla IMU yaw-rate channel hasn't been decoded yet. Don't try to compute yaw-rate residuals on Tesla CSVs — the truth channel isn't there. Only Ford CSVs carry yaw_rate_meas_rads.
- The KS model assumes the wheels are pointed in the direction the car goes. For real cars at any meaningful speed and lateral G, this is not true (slip angle is non-zero). That's *the workshop's whole point* — quantifying that residual.

## Module-specific note

> The team is currently observing the agent's context-window usage on the side (a context-window inspector tails the session log and renders token cost per turn). The expectation is that AGENTS.md + this CLAUDE.md together cost ~2000+ tokens *every turn* the agent runs. If a future iteration of this substrate refactors any of this content into on-demand skills, the per-turn cost should drop sharply. **For this run, please try to be efficient with context — avoid reading large files end-to-end if a targeted grep would do.**

## Notes the team meant to clean up but didn't

- The `tools/example_tool.py` file from the original template was deleted but its README still references it. Ignore the README; trust the actual file listing.
- The `_stage/` folder was also removed. If anything refers to it, ignore.
- The `references/` folder is empty. The team meant to put schema and glossary content here but hasn't yet.
- The `evals/` folder is empty. There are no automated evals to run against your work.
- The `skills/` folder is empty. There are no skills to discover.
