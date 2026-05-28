---
name: lateral-fidelity-triage
description: Run a disciplined variant ladder against Ford segments to improve lateral (yaw-rate) prediction fidelity, with strict marginal-RMSE accounting and a computational sensor that catches silent regressions. Use when the task is improving the lateral prediction of the KS model on a Ford platform. Produces REPORT.md with a per-regime variant table.
when-to-load: When the task names "lateral prediction", "yaw-rate residual", or "improve the lateral fidelity".
inputs: A list of Ford `sim.csv` paths (one per segment).
outputs: `REPORT.md` in the agent's working dir; intermediate variant CSVs under `out/`.
version: 0.5
changelog:
  - v0.1 — first crystallisation; bare-bones 5-step ladder.
  - v0.3 — added V0-baseline methodology pin after agent silently folded preprocessing into V0.
  - v0.4 — added ST low-v stiffness warning after agent re-discovered the eigenvalue blow-up.
  - v0.5 — added regression-flagging rule, single-markdown-table rule, and pegged-Cα detection. Sensor.py wired in as the final-check gate.
---

# lateral-fidelity-triage

## When to load

Load when:
- The task is improving lateral fidelity of a vehicle dynamics model.
- The data source is a Ford `sim.csv` with measured truth columns.

If the task wants longitudinal fidelity, this skill does not apply.

## Truth-channel discovery

Lateral-fidelity work uses **Ford** (Mach-E or Lightning). Tesla `sim.csv` has no decoded `yaw_rate_meas_rads` — the IMU isn't in the Tesla party DBC. Default to Mach-E; both Fords have measured truth.

## Operating contract — speed-known, lateral-only

KS runs with `clamp_v_to_measured=True` and `clamp_delta_to_measured=True`. So:

- `v` and `δ` are **inputs**; their state is overwritten by measurement each step. Speed-state agreement is zero by construction and is **not** the metric.
- Prediction channels: `yaw_rate_pred_rads`, `a_y_pred_mps2`.
- Truth channels (Ford only): `yaw_rate_meas_rads`, `a_lat_meas_mps2`.
- Residual under test: `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` (pre-computed).

Do **not** "fix" lateral residuals by unclamping `v` or `δ` — the contract is scope, not bug.

## Baseline methodology — fixed, not a choice  *(v0.3)*

Compute the V0 baseline RMSE from the existing `yaw_rate_resid_rads` column **as-is**, with no preprocessing. Any preprocessing belongs **inside V1+**, not V0. Folding a fix into V0 hides the upgrade that earns it.

## The procedure (5 steps, fixed order)

### Step 0 — baseline (V0)

Compute `RMSE(yaw_rate_resid_rads)` on the chosen Ford segment set. Apply the regime mask to compute per-regime numbers.

### Step 1 — KS recalibrated (V1)

Re-derive `ψ̇_KS = (v / L) · tan(δ_road)` using canonical `L` from `code/parameters.py`. Subtract a per-segment yaw-gyro bias on straight-line samples (mean residual where `|δ_road| < 0.01`).

Helper: `triage.ks_yaw_rate(v, delta_road, L)`.

### Step 2 — Linear ST with prior `C_α` (V2)

Steady-state linear-bicycle yaw-rate gain:

```
ψ̇_ST = v · δ / (L · (1 + K_us · v²))
K_us = m · (l_r·C_αr − l_f·C_αf) / (L² · C_αf · C_αr)
```

- Parameters from `PARAM_BY_PLATFORM`.
- **Low-speed stiffness  *(v0.4)*.** ST eigenvalues scale as `(C_αf + C_αr) / (m · v)`; they blow up as `v → 0`. Sub-step or fall back to KS below `v_min ≈ 2 m/s`. Ford Lightning segments include stationary stretches, so this matters.

Helper: `triage.linear_st_yaw_rate(...)` (handles the v_min fallback).

### Step 3 — Linear ST with fit `C_α` (V3)

Fit `C_αf, C_αr` on the segment set by minimising residual RMSE. Bounded to `(5e4, 5e5)` N/rad.

- **Pegged-at-upper-bound check  *(v0.5)*.** If either parameter pegs at the upper bound, the ST prior is already stiffer than these tyres need; V3 may be *worsening* relative to V1. Report as a regression with cause, not as a quiet win.

Helper: `triage.fit_c_alpha(df, L, l_f, l_r, m, I_z)` returns `(cf, cr, pegged)`.

### Step 4 — residual learner (V4)

Train a small ML residual model on `[v, |a_y|, |δ|, sign(δ̇)]` against V3's residuals.

- Use `sklearn.linear_model.Ridge`. Keep it small.
- **Leave-one-segment-out cross-validation only.** In-fold scoring is dishonest.
- If V4 doesn't beat V3 out-of-fold, ship V3 and call V4 a regression. Partial > faked.

Helper: `triage.residual_learner_loo(df)`.

## Regime mask (held constant across every variant row)

- **straight** — `|delta_road_rad| < 0.01 rad`
- **steady cornering** — `|δ| ≥ 0.01 rad` AND `|d δ/dt| < 0.05 rad/s`
- **transient cornering** — `|δ| ≥ 0.01 rad` AND `|d δ/dt| ≥ 0.05 rad/s`

Helper: `triage.regime_mask(df)`.

## Attribution accounting

Default: **strict marginal**, fixed order V0→V1→V2→V3→V4. Each variant's marginal drop is `RMSE(V_{i-1}) − RMSE(V_i)`. Marginal drops should sum to within **15%** of the total drop V0→V_last. If off by more than 15%, you have overlap or instability between two variants — investigate.

State the accounting scheme in the report.

## Reporting rules  *(v0.5)*

`REPORT.md` must:

- Name the platform you used and state explicitly that `yaw_rate_meas_rads` is **measured** truth.
- State that `v` and `δ` are **clamped** to measured under the speed-known contract.
- Contain **exactly one** markdown table — the variant ladder. Use bullet lists for everything else. (Downstream report-parsers latch onto the first markdown table; a second table will desync them.)
- Per-regime breakdown column.
- Honestly flag regressions: any variant that made things worse, with a physical reason.

## Sensor (mandatory final gate)  *(v0.5)*

Before declaring a "best variant", run:

```bash
python3 skills/lateral-fidelity-triage/sensor.py <best_variant.csv>
```

`sensor.py` is a deterministic regression guard. It loads a CSV with columns `[yaw_rate_pred_rads, yaw_rate_meas_rads]` and checks two properties:

1. `corr(pred, meas) > 0` on the cornering subset — guards against sign-flips.
2. `RMSE(pred − meas) ≤ RMSE_V0` — guards against silent regressions past the unrecalibrated baseline.

If either check fails, the variant is broken and must not be shipped. Patch the procedure, not the sensor.

## Sign-error checklist

If `corr(δ_road, ψ̇_meas)` is negative on a sustained-cornering segment: sign error. Check `delta_road_rad = -deg2rad(delta_wheel_deg) / i_s` — the leading minus is intentional; `i_s > 0`.
