---
name: lateral-fidelity-triage
description: Run a variant ladder against Ford segments to improve lateral (yaw-rate) prediction fidelity of the KS model. Use when the task is improving the lateral prediction on a Ford platform. Produces REPORT.md with a per-variant table.
when-to-load: When the task names "lateral prediction", "yaw-rate residual", or "improve the lateral fidelity".
inputs: A list of Ford `sim.csv` paths (one per segment).
outputs: `REPORT.md` in the agent's working dir; intermediate variant CSVs under `out/`.
version: 0.1
---

# lateral-fidelity-triage

First crystallisation by the domain expert. Covers the easy half of the work — picks the right data source, names the operating contract, walks a ladder of upgrades. Known to be incomplete; the team will patch it after the first reliability sweep.

## When to load

Load when:
- The task is improving lateral fidelity of a vehicle dynamics model.
- The data source is a Ford `sim.csv` with measured truth columns.

## Truth-channel discovery

Lateral fidelity work uses **Ford** (Mach-E or Lightning). Tesla `sim.csv` has no decoded `yaw_rate_meas_rads` column — the IMU isn't in the Tesla party DBC. Default to Mach-E for the first pass; both Fords have measured truth.

## Operating contract — speed-known, lateral-only

KS runs with `clamp_v_to_measured=True` and `clamp_delta_to_measured=True`. So:

- `v` and `δ` are **inputs**; their state is overwritten by measurement each step.
- The prediction channels are `yaw_rate_pred_rads` and `a_y_pred_mps2`.
- The truth channels (Ford only) are `yaw_rate_meas_rads` and `a_lat_meas_mps2`.
- The residual under test is `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` (pre-computed in the CSV).

## The procedure (5 steps)

### Step 0 — baseline (V0)

Compute `RMSE(yaw_rate_resid_rads)` on the chosen Ford segment set. Use the regime mask below to compute per-regime numbers too.

### Step 1 — KS recalibrated (V1)

Re-derive `ψ̇_KS = (v / L) · tan(δ_road)` using the canonical `L` from `code/parameters.py`. Subtract a per-segment yaw-gyro bias on straight-line samples (mean residual where `|δ_road| < 0.01`).

Helper: `triage.ks_yaw_rate(v, delta_road, L)`.

### Step 2 — Linear ST with prior `C_α` (V2)

Switch to the linear single-track steady-state gain. Use openpilot's prior `C_alpha_f, C_alpha_r` from `parameters.py`.

```
ψ̇_ST = v · δ / (L · (1 + K_us · v²))
K_us = m · (l_r·C_αr − l_f·C_αf) / (L² · C_αf · C_αr)
```

Helper: `triage.linear_st_yaw_rate(...)`.

### Step 3 — Linear ST with fit `C_α` (V3)

Fit `C_αf, C_αr` to the segment set by minimising residual RMSE. Bounded to `(5e4, 5e5)` N/rad.

Helper: `triage.fit_c_alpha(df, L, l_f, l_r, m, I_z)`.

### Step 4 — residual learner (V4)

Train a small ML residual model on `[v, |a_y|, |δ|, sign(δ̇)]` against V3's residuals. Use `sklearn.linear_model.Ridge`. Cross-validate.

Helper: `triage.residual_learner_loo(df)` — leave-one-segment-out.

## Regime mask

- **straight** — `|delta_road_rad| < 0.01 rad`
- **steady cornering** — `|δ| ≥ 0.01 rad` AND `|d δ/dt| < 0.05 rad/s`
- **transient cornering** — `|δ| ≥ 0.01 rad` AND `|d δ/dt| ≥ 0.05 rad/s`

Helper: `triage.regime_mask(df)`.

## Reporting

`REPORT.md` must include:

- Which Ford platform you scored on; statement that `yaw_rate_meas_rads` is **measured** truth.
- A variant ladder V0→V4 with per-regime RMSE columns.
- An attribution column for each variant's contribution.

## Sign-error checklist

If `corr(δ_road, ψ̇_meas)` is negative on a cornering segment: sign error. Check `delta_road_rad = -deg2rad(delta_wheel_deg) / i_s`.
