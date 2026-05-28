# AGENTS.md — webinar-angle-E / module-2 (workflow tier)

This module is the **workflow** rung of the four-scaffold comparison. The control flow is hard-coded; each step is a focused, narrowly-scoped action you execute against a pre-built deterministic tool. You do not improvise the steps, you do not skip ahead, and you do not invent new variants outside the ladder. Each step has a single tool wrapper under `tools/`; call them in order.

## Why this is a workflow, not an agent

The point of this module is **the workflow tier of NC-6**. If you could draw the procedure on a whiteboard before you started — which you could, because we have — then a hand-built workflow is the right shape. You are the deterministic executor; the LLM judgement is bounded inside each step.

## Project context

Sim-real correlation runtime around the CommonRoad **kinematic single-track (KS)** vehicle dynamics model. The lateral residual under test is `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` (pre-computed in each Ford `sim.csv`).

- KS implementation: `code/ks_model.py`.
- Sim CSV producers: `code/generate_simdata_ford.py`. Output at `data/sim/segments/<PLATFORM>/<device>/<route>/<idx>/sim.csv`.
- Vehicle parameters: `code/parameters.py::PARAM_BY_PLATFORM[platform_str]`.
- Python 3 on PATH with `pandas`, `numpy`, `scipy`, `matplotlib`, `sklearn` installed. Use `python3`, never `python`. No venv.

## Operating contract (constant across the workflow)

KS runs with `clamp_v_to_measured=True` and `clamp_delta_to_measured=True`. Speed and steering are inputs; the lateral residual is the only metric. Do not "fix" lateral residuals by unclamping `v` or `δ`.

## The workflow — five steps, in order

Run each step exactly as the corresponding script in `tools/` prescribes. Each script accepts `--help`.

```
tools/
  step1_load_ford_segments.py     ← collect Ford `sim.csv` paths + load into a single DataFrame
  step2_segment_by_regime.py      ← add `regime` column (straight / steady / transient)
  step3_compute_residuals.py      ← compute V0 per-regime RMSE on `yaw_rate_resid_rads`
  step4_run_st_upgrade.py         ← apply Linear-ST upgrade with fit Cα; emit V1/V2/V3 residuals
  step5_write_report_skeleton.py  ← produce REPORT.md skeleton; you fill in the prose
```

### Step 1 — Load

```bash
python3 tools/step1_load_ford_segments.py --platform FORD_MUSTANG_MACH_E_MK1 --out out/df.parquet
```

Loads every Ford Mach-E `sim.csv` under `data/sim/segments/...` into a single DataFrame; saves to `out/df.parquet`. Validates required columns; refuses on missing.

### Step 2 — Segment

```bash
python3 tools/step2_segment_by_regime.py --in out/df.parquet --out out/df_regime.parquet
```

Adds a `regime` column with values `{straight, steady, transient}` using fixed thresholds (`|δ| < 0.01` straight; `|d δ/dt| < 0.05 rad/s` steady).

### Step 3 — Residuals

```bash
python3 tools/step3_compute_residuals.py --in out/df_regime.parquet --out out/v0_rmse.json
```

Writes per-regime + overall V0 RMSE to JSON. **No preprocessing.**

### Step 4 — ST upgrade

```bash
python3 tools/step4_run_st_upgrade.py --in out/df_regime.parquet --platform FORD_MUSTANG_MACH_E_MK1 --out out/v1_v2_v3.json
```

Applies, in fixed order:
  - **V1** — KS recalibrated (re-derive ψ̇ from canonical `L`; subtract per-segment yaw-gyro bias on straight rows).
  - **V2** — Linear ST with openpilot prior `C_α`.
  - **V3** — Linear ST with fit `C_α` (L-BFGS-B on Cα within `(5e4, 5e5)` N/rad).

Writes per-regime + overall RMSE for V1/V2/V3 to JSON. Includes a `pegged` flag if the fit hit the upper bound (then V3 is a regression flag).

### Step 5 — Report

```bash
python3 tools/step5_write_report_skeleton.py --rmse-files out/v0_rmse.json out/v1_v2_v3.json --out REPORT.md
```

Writes a skeleton `REPORT.md` with the variant ladder table populated from the JSON files. You add the prose: platform statement, contract statement, attribution column, regression flag, any honest caveats.

## What's deliberately missing

- No catalogue, no skill, no eval. The workflow IS the substrate.
- No room to invent V4 (residual learner). The ladder stops at V3 here. If V3 pegs at the upper bound, you flag it as a regression and stop.
- No room to switch platforms mid-workflow.

If you find yourself wanting to deviate, that is signal for the workshop — record it and report it. Do not deviate.

## Reporting (final deliverable)

`REPORT.md` at the module root. Use the skeleton step 5 produced.
