---
title: CommonRoad spine — runnable code
summary: Minimal Python implementation of the workshop's KS (kinematic single-track) model with parameter sets for three platforms (Tesla Model 3, Ford Mustang Mach-E, Ford F-150 Lightning) — all openpilot-canonical, read from carParams in actual rlogs. Real-data runs operate in **speed-known lateral-only** mode: measured `v` and measured `δ` are clamped at every integration step (see ../models.md § "Speed-known framing"). Runnable demos: (1) synthetic open-loop; (2) real Tesla rlog → KS via opendbc Tesla party DBC; (3) real Ford rlog (Mach-E + F-150) → KS via opendbc ford_lincoln_base_pt DBC, with measured yaw-rate and lateral-acceleration truth channels in the output CSV alongside the KS lateral prediction and the residual.
tags: [code, commonroad, ks-model, lateral-only, speed-known, tesla, ford, mach-e, f-150-lightning, numpy, matplotlib, pycapnp, cantools, opendbc]
updated: 2026-05-25
---

# CommonRoad spine — runnable code

This directory is the runnable counterpart of [`../`](../). The docs explain *what* and *why*; the code is *how*. Mirrors the docs one-to-one.

## Operating mode

Real-data runs operate in **speed-known lateral-only** mode (see [../models.md § "Speed-known framing"](../models.md) and [../_README.md § "Scope decision"](../_README.md)). Mechanically this means [`simulate_ks`](ks_model.py) is called with `clamp_v_to_measured=True` *and* `clamp_delta_to_measured=True`. The integrator still runs `dv/dt = a` and `dδ/dt = δ̇` internally, but their results are overwritten by the measured values at every step. Effectively:

- The model's longitudinal channel is an **input**, not an output. Speed-state-vs-measured agreement is zero by construction (verified at the end of each generator's smoke output) — *do not interpret this as model fidelity*.
- The model's lateral channel — yaw rate, lateral acceleration, heading, planar trajectory — is what gets predicted. The Ford CSVs include the measured yaw rate and lateral acceleration alongside the prediction so the residual is computable directly.
- `KSDriverInputs.a` and `KSDriverInputs.delta_dot` are still populated (from the IMU and from `gradient(δ_meas)` respectively), but the integrator ignores them under the clamps. They live in the CSV for *side-panel* analyses — e.g. the difference between IMU `a_long` and `d(v_meas)/dt` is grade + powertrain + sensor bias, recoverable as a longitudinal-residual demo without involving the model.

To run the model open-loop instead (no clamping), set both flags to `False` when calling `simulate_ks`. The synthetic demo `run_ks_synthetic.py` already uses this mode because there is no measurement to clamp against.

## What runs today

```bash
# Synthetic input — pure numpy, no rlog dependency. Produces out/ks_synthetic.png in ~1s.
python run_ks_synthetic.py

# Plot sim.csvs that the build-simdata skill has produced under data/sim/segments/<PLATFORM>/.
python plot_simdata.py            # Tesla
python plot_simdata_ford.py       # Ford
```

Setup (once):

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install pycapnp zstandard cantools numpy scipy matplotlib pandas
```

The data pipeline lives in two skills under [`../webinar-meta/skills/`](../webinar-meta/skills/) and uses `code/` only as a library:

| Skill | What it does | Reads from `code/` |
|---|---|---|
| [download-rlog-data](../webinar-meta/skills/download-rlog-data/) | Discovery / suitability / download of raw rlogs (replaces the old `code/fetch_*.py` scripts). | — |
| [build-simdata](../webinar-meta/skills/build-simdata/) | Decodes rlog → KS-baseline sim.csv → truth-stripped sim-only/.  Owns the per-OEM adapters and DBCs (moved from `code/_schema/dbc/`). | `ks_model.py`, `parameters.py`, `rlog_reader.py` |

The cereal capnp schema (from `commaai/openpilot`) is pinned in [`_schema/cereal/`](_schema/cereal/) — DBCs moved with the adapters into the build-simdata skill.

## Files

| File | Purpose | Status |
|---|---|---|
| [parameters.py](parameters.py) | KS + ST parameter dataclasses for Tesla Model 3, Ford Mustang Mach-E, Ford F-150 Lightning, and Hyundai Ioniq 5 — every value openpilot-canonical, sourced from rlog carParams. Exposes `PARAM_BY_PLATFORM` for platform-keyed lookup. Imported by build-simdata and by agents. | library |
| [ks_model.py](ks_model.py) | KS ODE (`ẋ = f(x, u; p)`) plus an RK4 integrator. Smoke test traces a circle of radius L/tan(δ) to four decimals. Vehicle-agnostic — consumes any KS parameter dataclass. Imported by build-simdata and by agents. | library |
| [rlog_reader.py](rlog_reader.py) | Lightweight rlog decoder using pycapnp + the pinned cereal schema. Vehicle-agnostic. Imported by every adapter in build-simdata. | library |
| [synthetic_inputs.py](synthetic_inputs.py) | Synthetic `(δ(t), a(t))` traces for the no-rlog demo | runnable |
| [run_ks_synthetic.py](run_ks_synthetic.py) | Six-panel matplotlib figure of KS on a synthetic 60-s drive | runnable |
| [plot_simdata.py](plot_simdata.py) | Tesla: renders one PNG per sim.csv alongside it | runnable |
| [plot_simdata_ford.py](plot_simdata_ford.py) | Ford: renders one PNG per sim.csv showing KS prediction overlaid on measured yaw rate and lateral G, plus residual time series. | runnable |
| [inspect_rlog.py](inspect_rlog.py) | Open one rlog and dump service-by-service counts and rates | runnable |
| [_schema/cereal/](_schema/cereal/) | Pinned cereal capnp schema (do not edit; bump COMMIT.txt to refresh). DBC files moved with the adapters to [../webinar-meta/skills/build-simdata/_schema/dbc/](../webinar-meta/skills/build-simdata/_schema/dbc/). | pinned |
| [out/](out/) | Output figures from the synthetic demo | generated |

## Map back to the docs

- [parameters.py](parameters.py) is the executable form of the parameter tables in [../vehicle-tesla-model-3.md](../vehicle-tesla-model-3.md), [../vehicle-mach-e.md](../vehicle-mach-e.md), and [../vehicle-f150-lightning.md](../vehicle-f150-lightning.md). Every numeric value is openpilot-canonical (decoded from the rlog `carParams` event).
- [ks_model.py](ks_model.py) is the executable form of the "KS — Kinematic Single-Track" section of [../models.md](../models.md). Every state and equation in the doc has a corresponding line of code.
- [rlog_reader.py](rlog_reader.py) plus the adapters in [../webinar-meta/skills/build-simdata/_adapters/](../webinar-meta/skills/build-simdata/_adapters/) are the executable form of the adapters layer. The Tesla adapter is the harder path (no decodable IMU); Ford + Hyundai exercise the easier path (first-class / patchable openpilot port — yaw rate read straight from the open DBC).
- [../webinar-meta/skills/build-simdata/build_simdata.py](../webinar-meta/skills/build-simdata/build_simdata.py) is the workshop's "now we plug in real data" beat. Output lives under `data/sim/segments/<PLATFORM>/` (full) and `data/sim-only/segments/<PLATFORM>/` (truth-stripped, agent-facing).

## Next sessions

1. **Add an ST model** (`st_model.py`) — same dataclass shape, different `f`; ST's lateral states (`ψ̇`, `β`) integrate forward, but under the speed-known scope `v` is still clamped. ST parameters are already pinned in [parameters.py](parameters.py) for all three platforms. The Ford yaw-rate truth channel (already in the CSVs) becomes the calibration target for `C_α,f` / `C_α,r`.
2. **Decode Tesla's IMU on CAN.** The party DBC exposes the QF bits for yaw/lat/long accel but not the values. Find the message that broadcasts them. Until then, Tesla simdata has the KS lateral *prediction* (since both inputs are speed-known) but no measured-vs-predicted yaw-rate comparison; Ford simdata has both.
3. **Build the visual diff** in rerun.io: KS prediction + measured truth, time-aligned. See [../../viz-options.md](../../viz-options.md) for the full comparison. The Ford CSVs already include both channels so the rerun layout can be built off them today.
4. **Longitudinal decomposition side panel.** The difference between IMU `a_long` and `d(v_meas)/dt` carries grade + EV powertrain + sensor bias. Write the explicit decomposition (low-frequency = grade; lift-off + brake transients = regen; constant offset = bias) as a side-panel demo that complements the lateral spine without being on it.
