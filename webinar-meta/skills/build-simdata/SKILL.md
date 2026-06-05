---
name: build-simdata
description: Decode raw rlog.zst CAN logs into KS-baseline sim.csv files, then strip truth columns to produce sim-only.csv for agent consumption. Replaces the per-OEM generate_simdata_*.py scripts with one CLI that dispatches by platform name; processes both train and val roots in parallel; runs the same V0 baseline (`simulate_ks(clamp_v=True, clamp_delta=True)`) that the grader scores against.
when-to-load: After downloading a new platform with download-rlog-data, or after adding a new OEM adapter, or whenever the sim-only schema bumps and you need to refresh existing tree without re-decoding. Also when the user asks "what's been built", "what platforms have sim data", or "rebuild simdata for X".
inputs: A platform id (e.g. FORD_F_150_LIGHTNING_MK1, HYUNDAI_IONIQ_5) whose raw/ tree exists under data_root or val_data_root. No-args run = discovery view (per-platform raw/sim/sim-only counts + adapter availability).
outputs: <data_root>/sim/segments/<PLATFORM>/<dev>/<route>/<idx>/sim.csv (full, with truth channels) + <data_root>/sim-only/segments/.../sim.csv (truth-stripped, 8-column schema) + manifest.json per platform. Val mirror under <val_data_root>.
load-cost: ~250 tokens metadata, ~850 tokens body.
---

# build-simdata

## Pipeline position

```
download-rlog-data  →  raw/segments/<PLATFORM>/.../rlog.zst
                            │
                            ▼  build-simdata  (this skill)
                            │
                       sim/segments/<PLATFORM>/.../sim.csv         ← full: decoded + V0 KS prediction + truth
                            │
                            ▼  (sim-only projection)
                            │
                       sim-only/segments/<PLATFORM>/.../sim.csv    ← 8-column agent-facing schema
                            │
                            ▼  grade-cohort-reports / agent predict()
```

The same shape applies to the val side (`<val_data_root>/...`). Roots come from [webinar-meta/data-paths.json](../../data-paths.json) — single source of truth.

## How to use

### Discovery (always start here)

```bash
python webinar-meta/skills/build-simdata/build_simdata.py
```

Walks both train and val trees, prints a per-platform table of `raw / sim / sim-only` counts plus whether an adapter is registered. Use this to see what needs building and to spot inconsistencies (e.g. sim < raw means partial build).

### Build one platform

```bash
# Decode + simulate + sim-only, both sides, all segments
python webinar-meta/skills/build-simdata/build_simdata.py HYUNDAI_IONIQ_5

# Restrict to one side
python webinar-meta/skills/build-simdata/build_simdata.py TESLA_MODEL_3 --side train

# Smoke test on the first 2 segments only
python webinar-meta/skills/build-simdata/build_simdata.py FORD_F_150_LIGHTNING_MK1 --limit 2

# Skip the sim-only projection (e.g. while iterating on an adapter)
python webinar-meta/skills/build-simdata/build_simdata.py FORD_MUSTANG_MACH_E_MK1 --no-sim-only

# Adjust parallelism (default 4 process workers)
python webinar-meta/skills/build-simdata/build_simdata.py HYUNDAI_IONIQ_5 --workers 8
```

Re-runs are cheap — any segment whose sim.csv already exists and is non-empty is skipped.

### Refresh sim-only after a schema change

If you update the sim-only column allowlist or any per-platform projection map, regenerate the truth-stripped tree without paying the decode cost:

```bash
python webinar-meta/skills/build-simdata/build_simdata.py HYUNDAI_IONIQ_5 --refresh-sim-only
```

## Runtime requirements

Needs `cantools`, `pycapnp`, `zstandard`, `numpy`. Use any project venv that has these — the existing F1/KB003 venv works:

```bash
/Users/javiquix/Desktop/quixdev/F1/KB003/.venv/bin/python webinar-meta/skills/build-simdata/build_simdata.py ...
```

Or create one locally:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install pycapnp zstandard cantools numpy
```

## Files

| File | Role |
|---|---|
| `build_simdata.py` | Single CLI. Discovery view (no args), per-OEM dispatch, parallel build, sim-only projection, manifest writer. |
| `_adapters/adapter_tesla_rlog.py` | Tesla CAN decoder (party DBC). No truth channels (party DBC ships only quality bits). |
| `_adapters/adapter_ford_rlog.py` | Ford CAN decoder (ford_lincoln_base_pt DBC). Surfaces yaw rate + lateral G as truth. Handles Mach-E + F-150 Lightning. |
| `_adapters/adapter_hyundai_rlog.py` | Hyundai E-GMP CAN-FD decoder (hyundai_canfd DBC, `strict=False`). Surfaces yaw rate + lateral G. Covers Ioniq 5 (and other E-GMP platforms by extension). |
| `_schema/dbc/` | Pinned DBC files (commit SHA in `COMMIT.txt`). Do not edit; bump the COMMIT.txt note to refresh. |

The skill **imports** from `code/`: `ks_model.py` (the V0 baseline), `parameters.py` (per-platform parameter dataclasses), `rlog_reader.py` (vehicle-agnostic capnp reader). Those stay in `code/` because agents reference them too.

## sim-only contract

The 8-column agent-facing schema is fixed:

```
t_s, delta_wheel_deg, delta_road_rad, v_mps, a_long_mps2,
accel_pedal_pct, brake_pressed, yaw_rate_pred_rads
```

Truth-bearing columns (`yaw_rate_meas_rads`, `a_lat_meas_mps2`, `*_resid_*`, integrated `x_m`/`y_m`/`psi_rad`, internal states) are **stripped by construction** — agents can never see them in the file `predict()` consumes. The `SIM_ONLY_MAPS` dict in `build_simdata.py` defines the per-OEM source-column lookup (with optional transforms — e.g. Tesla's `brake_pedal_state` enum becomes a `brake_pressed` bool; Hyundai's missing pedal channels emit empty strings).

If the challenge ever needs a different column set, change `SIM_ONLY_HEADERS` + the per-OEM maps and run `--refresh-sim-only` per platform.

## Adding a new OEM — recipe

1. **Confirm suitability.** Run [../download-rlog-data/recommend.py](../download-rlog-data/recommend.py) to see whether the OEM's DBC exposes decoded yaw rate. If verdict is `no`, this skill cannot give you truth-channel sim data — the OEM is off the table for lateral-fidelity work.
2. **Pin the DBC.** Download the right `.dbc` from [commaai/opendbc](https://github.com/commaai/opendbc) at a committed SHA. Drop it in `_schema/dbc/` and add an entry to `_schema/dbc/COMMIT.txt`. If the DBC ships as generator fragments only (Hyundai CAN-FD), concatenate them and note that in COMMIT.txt.
3. **Inspect a sample rlog** to find the right CAN addresses:
   ```bash
   python code/inspect_rlog.py data/raw/segments/<PLATFORM>/<dev>/<route>/0/rlog.zst
   ```
   Then write a small probe to print the address distribution (see the long-form recipe in the prior conversation under "Scan Ioniq CAN addresses").
4. **Author `adapter_<oem>_rlog.py`** in `_adapters/`. Use `adapter_ford_rlog.py` as the template — it's the cleanest. The adapter exports `load_segment_measurements(rlog_path, steer_ratio, sample_rate_hz)` returning a `SegmentMeasurements`-like dataclass with at least: `t`, `delta_wheel_deg`, `delta_road_rad`, `v_mps`, `a_long_mps2`. If the OEM ships yaw rate / lat-G truth: also `yaw_rate_rads`, `a_lat_mps2`.
5. **Add the parameter dataclass** to [../../../code/parameters.py](../../../code/parameters.py) — wheelbase, mass, inertia, steer ratio, etc., all read from `carParams` in any sample rlog of that platform. Register in `PARAM_BY_PLATFORM`.
6. **Register the builder** in `build_simdata.py`:
   ```python
   def _build_<oem>(rlog_path, platform): ...
   BUILDERS["<OEM_PREFIX>"] = _build_<oem>
   SIM_ONLY_MAPS["<OEM_PREFIX>"] = {...}   # column projection for sim-only
   ```
7. **Smoke-test** on one segment:
   ```bash
   python build_simdata.py <PLATFORM> --side train --limit 1 --workers 1
   ```
   Inspect the resulting sim.csv; cross-check against the OEM's expected residual scale.

For E-GMP cousins (Kia EV6, Genesis GV60) sharing the same Hyundai DBC, you only need steps 5–6: the adapter is already there; register the params + a new `BUILDERS["KIA"]` alias.

## What this skill does NOT do

- Does not download rlogs — that's [download-rlog-data](../download-rlog-data/).
- Does not modify `ks_model.py` or `parameters.py` — those are owned by `code/` and read by agents too.
- Does not write the cohort report — that's [grade-cohort-reports](../grade-cohort-reports/).
- Does not validate signals against a ground truth — the V0 baseline is the model under test; agents' job is to beat it.
