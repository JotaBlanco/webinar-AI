---
name: lateral-fidelity-triage
description: Run a disciplined variant ladder against Ford segments to improve lateral (yaw-rate) prediction fidelity, with strict marginal-RMSE accounting. Use when the task is improving the lateral prediction of the KS model on a Ford platform. Produces a single REPORT.md with a per-regime variant table and attribution column.
when-to-load: When the task names "lateral fidelity", "yaw-rate residual", or "improve the lateral prediction".
inputs: A list of Ford `sim.csv` paths (one per segment).
outputs: `REPORT.md` in the agent's working dir; intermediate variant CSVs under `out/`.
---

# lateral-fidelity-triage

## When to load this skill

Load when:
- The task is to improve lateral fidelity of a vehicle dynamics model.
- The data source is a Ford `sim.csv` with measured truth columns.

If the task wants longitudinal fidelity, this skill does not apply.

## The procedure (5 fixed steps, in this order)

### Step 0 — baseline (V0)

Compute `RMSE(yaw_rate_resid_rads)` across the full Ford-segment set, **with no preprocessing**. This is V0. Apply the regime mask (defined below) to compute per-regime numbers.

> **Discipline.** The baseline is the `yaw_rate_resid_rads` column as-is. Any preprocessing belongs in V1+, not V0. Folding a fix into V0 hides the upgrade that earns it.

### Step 1 — KS recalibrated (V1)

Re-derive `ψ̇_KS = (v / L) · tan(δ_road)` using the canonical `L` from `code/parameters.py::PARAM_BY_PLATFORM`. Optionally subtract a per-segment yaw-gyro bias (mean residual on straight-line samples). Report what you subtracted.

Helper: `triage.ks_yaw_rate(v, delta_road, L)`.

### Step 2 — Linear ST with prior `C_α` (V2)

Switch to the linear single-track steady-state gain. Use openpilot's prior `C_alpha_f, C_alpha_r` from `parameters.py`. Cross-check that ST predicts a positive yaw rate when steering is positive (else: sign error). At low `v → 0`, ST eigenvalues blow up — sub-step or fall back to KS below `v_min ≈ 2 m/s`.

Helper: `triage.linear_st_yaw_rate(...)`.

### Step 3 — Linear ST with fit `C_α` (V3)

Fit `C_αf, C_αr` to the segment set by minimising residual RMSE. Bounded to (5e4, 5e5) N/rad. **If the fit pegs at the upper bound, report it as a regression / overfit flag** and discuss why (likely: ST prior already too stiff for these tyres, so the fit is closing the wrong gap).

Helper: `triage.fit_c_alpha(df, L, l_f, l_r, m, I_z)`.

### Step 4 — residual learner (V4)

Train a small ML residual model on `[v, |a_y|, |δ|, sign(δ̇)]` against V3's residuals.

- Use `sklearn.linear_model.Ridge` or similar. Keep it small.
- **Leave-one-segment-out cross-validation only.** In-fold scoring is dishonest.
- If V4 doesn't beat V3 out-of-fold, ship V3 and call V4 a regression. Partial > faked.

## Regime mask (held constant across every variant row)

- **straight** — `|delta_road_rad| < 0.01 rad`
- **steady cornering** — `|delta_road_rad| ≥ 0.01 rad` AND `|d(delta_road_rad)/dt| < 0.05 rad/s`
- **transient cornering** — `|delta_road_rad| ≥ 0.01 rad` AND `|d(delta_road_rad)/dt| ≥ 0.05 rad/s`

Helper: `triage.regime_mask(df)`.

## Attribution accounting

Default scheme: **strict marginal**, in the fixed order V0→V1→V2→V3→V4. Each variant's "marginal drop" is `RMSE(V_{i-1}) − RMSE(V_i)`. Marginal drops should sum to within **15%** of the total drop V0→V_last. If your accounting is off by more than 15%, you have either an overlap between two variants or a numerically unstable variant — investigate.

State the accounting scheme in the report.

## Reporting

`REPORT.md` must:

- Name the platform you used and explicitly state that `yaw_rate_meas_rads` is **measured** (not predicted, not clamped).
- State that `v` and `δ` are **clamped** to measured under the speed-known contract.
- Contain **exactly one** markdown table — the variant ladder. Use bullet lists or paragraphs for everything else. (Downstream matchers latch onto the first markdown table.)
- Include a per-regime breakdown column.
- Honestly flag regressions: any variant that made things worse, with a physical reason.

After producing `REPORT.md`, if `evals/` is present, run `python3 evals/lateral_fidelity_eval.py REPORT.md`. If it fails, patch **this SKILL.md** (not the eval) and re-run.
