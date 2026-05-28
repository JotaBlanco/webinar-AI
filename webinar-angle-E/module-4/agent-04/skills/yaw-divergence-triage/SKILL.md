---
name: yaw-divergence-triage
description: Improve lateral (yaw-rate) prediction fidelity of the KS model on a Ford segment set by walking a fixed variant ladder (V0 → V1 KS recalib → V2 Linear ST prior → V3 Linear ST fit) with strict marginal-RMSE accounting. Produces a REPORT.md with platform, contract statement, variant table, attribution column, regression flags.
when-to-load: When the task is improving lateral prediction, yaw-rate residual, or any "vehicle model isn't as good as it should be" framing where the data has measured truth.
inputs: A platform name (FORD_MUSTANG_MACH_E_MK1 or FORD_F_150_LIGHTNING_MK1).
outputs: `REPORT.md` in the working directory; per-variant artifacts under `out/`.
version: 1.0
---

# yaw-divergence-triage

## When to load

Load when the task wants to improve lateral fidelity of a vehicle dynamics model and a Ford `sim.csv` with measured truth columns is available. Skip for longitudinal-fidelity tasks (no truth channel).

## Truth-channel discovery

Lateral-fidelity work uses **Ford** (Mach-E or Lightning). Tesla `sim.csv` has no `yaw_rate_meas_rads`. Default to Mach-E unless the task says otherwise.

## Operating contract

`v` and `δ` are clamped to measured. Speed-state agreement is zero by construction; it is **not** the metric. Do not unclamp to "fix" the residual.

## The procedure (5 steps in order)

### Step 0 — baseline (V0)

Load Ford `sim.csv` files into a DataFrame; compute `RMSE(yaw_rate_resid_rads)` overall and per regime. **No preprocessing** — the V0 baseline is the column as it sits.

### Step 1 — KS recalibrated (V1)

Re-derive `ψ̇_KS = (v / L) · tan(δ_road)` using canonical `L` from `parameters.py::PARAM_BY_PLATFORM`. Subtract a per-segment yaw-gyro bias computed on straight-line samples (mean residual where `|δ_road| < 0.01`).

Helper: `triage.v1_ks_recalibrated(df, platform)`.

### Step 2 — Linear ST, prior `C_α` (V2)

Switch to the steady-state linear-bicycle gain:

```
ψ̇_ST = v · δ / (L · (1 + K_us · v²)),  K_us = m · (l_r·C_αr − l_f·C_αf) / (L² · C_αf · C_αr)
```

Use openpilot's prior `C_αf, C_αr` from `parameters.py`. **Low-v fallback** — ST eigenvalues blow up as `v → 0`; below `v_min = 2 m/s` fall back to KS. The Ford Lightning has stationary stretches; this matters.

Helper: `triage.v2_linear_st_prior(df, platform)`.

### Step 3 — Linear ST, fit `C_α` (V3)

Fit `C_αf, C_αr` to the segment set by minimising residual RMSE; bounded to `(5e4, 5e5)` N/rad.

**Pegged-bound check** — if either parameter pegs at the upper bound, the ST prior is already stiffer than these tyres want; V3 may be *worse* than V1 on some regimes. Report as a regression with cause.

Helper: `triage.v3_linear_st_fit(df, platform)` returns `(df_with_v3, fit_info)`.

## Regime mask

- straight — `|δ_road| < 0.01 rad`
- steady cornering — `|δ| ≥ 0.01` AND `|d δ/dt| < 0.05 rad/s`
- transient cornering — `|δ| ≥ 0.01` AND `|d δ/dt| ≥ 0.05 rad/s`

Helper: `triage.regime_mask(df)`.

## Attribution accounting

Strict marginal, fixed order V0→V1→V2→V3. Each variant's marginal drop is `RMSE(V_{i-1}) − RMSE(V_i)`. Marginal drops should sum to within **15%** of the total drop. State the accounting scheme in the report.

## Reporting

`REPORT.md` must contain:

- Platform statement (e.g., `FORD_MUSTANG_MACH_E_MK1`).
- Statement that `yaw_rate_meas_rads` is measured truth and that `v`/`δ` are clamped.
- One markdown table (the variant ladder) with per-regime columns. Use bullet lists for everything else.
- Attribution column.
- Honest regression flags where the metric got worse, with physical reason.

## Composition with the sibling skill

`regime-comparison/SKILL.md` is in the same folder. If you want to dig into *which* regime each variant most affects, run it on the per-variant DataFrames after step 3 and append its output as a sub-section under "Attribution". Optional, not mandatory.
