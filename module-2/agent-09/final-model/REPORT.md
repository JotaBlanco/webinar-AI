# Agent-09 lateral fidelity model — REPORT

## Headline results

Scored across all 415 Ford segments under `data/sim/segments/FORD_*` using
`skills/score-model/score.py` (sample-pooled yaw-rate RMSE with v > 2 m/s
filter; segment-then-bin-pooled CTE at 1 m grid step, min 20 m per segment).

| metric                | V0 baseline | Final model | improvement |
|-----------------------|-------------|-------------|-------------|
| yaw-rate RMSE (rad/s) |     0.01479 |     0.00773 |    -47.7 %  |
| CTE RMSE (m)          |    151.998  |    102.086  |    -32.8 %  |

Per-platform:

| platform                    | V0 yr   | Final yr | V0 cte | Final cte |
|-----------------------------|---------|----------|--------|-----------|
| FORD_MUSTANG_MACH_E_MK1     | 0.01362 | 0.00895  | 148.00 | 121.99    |
| FORD_F_150_LIGHTNING_MK1    | 0.01633 | 0.00555  | 157.51 |  63.87    |

Per-regime yaw-rate RMSE (final): straight 0.00628, steady 0.01163, transient 0.01763.

Held-out 80/20 split (seed=42): coefficients converged to the same values on
the train-only fit; dev-only yaw-rate RMSE 0.00791 vs 0.00773 on the full
set — generalisation is clean.

## What I implemented

Steady-state yaw rate from a linear bicycle with understeer gradient:

    yr_ss(t) = v(t) * (s * delta_road(t)) / (L + K * v(t)^2) + bias

driven through a first-order lag (time-constant tau) plus an integer sample
delay d (typically 0-1 samples on this 50 Hz data):

    delayed_ss[i] = yr_ss[i - d]                    # clamped at the start
    yr[i]         = (1 - a) * yr[i-1] + a * delayed_ss[i-1],   a = dt / (tau + dt)

Coefficients fit per platform on all 415 segments via scipy Nelder-Mead on
yaw-rate MSE (samples with v > 2 m/s). Integer delay swept on outer loop.

Fitted values (final shipped):
- Mach-E:    s = 1.2033, K = 0.00294, bias = +0.000214, tau = 0.032 s, delay = 1
- Lightning: s = 0.9773, K = 0.00392, bias = -0.00442,  tau = 0.023 s, delay = 1

The Mach-E `s = 1.20` is striking — `delta_road_rad` for the Mach-E appears
~17 % under-scaled vs what reproduces measured yaw rate. Lightning is at
s ≈ 1.0. Likely a steering-ratio / adapter quirk.

predict() also returns x_m / y_m, integrated identically to
`_shared/traj_metrics.integrate_trajectory` using measured v and the
predicted yaw rate.

## Skills usage

- `score-model/score.py` — used as-is, every iteration.
- `pre-flight-final-model/preflight.py` — ran before shipping; passes all
  checks except `report_md_present` (REPORT.md write is blocked in the
  sub-agent and is persisted by the parent).
- `make-train-dev-split/` — bypassed (inline numpy permutation, trivial).
- `load-segments/`, `compare-models/`, `visualise-segment/` — not loaded;
  pandas + the scorer covered the workflow.

## Variants tried

- **V1** (bicycle + understeer + per-platform scale + bias, no lag):
  YR 0.00844 / CTE 101.50. Most of the headline improvement comes from this.
- **V2** (V1 + first-order lag): YR 0.00774 / CTE 102.58. Lag hits
  transients (regime YR 0.0240 → 0.0178) but barely moves CTE since CTE is
  dominated by low-frequency angular error accumulation.
- **V3 shipped** (V2 + integer-sample input delay d): essentially identical
  to V2; delay 0-1 chosen per platform. Marginal Mach-E benefit.

## Residual structure (what's left)

- Symmetric residual std ~0.008 rad/s (Mach-E), ~0.005 rad/s (Lightning) —
  no obvious |delta| or v dependence inside the fit range.
- Mild high-speed (v > 30 m/s) bias of ~+0.002 rad/s on both platforms,
  suggesting the v² understeer term doesn't quite cover high-speed dynamics.
- Small left/right asymmetry in residual mean (~±0.001 rad/s) — visible but
  too small to justify directional coefficients.

## What I didn't try (and why)

- **Per-segment bias correction from yaw_rate_meas in sim_df**: would have
  helped CTE further but is reading the truth channel from the input — judged
  as bleeding the metric.
- **Full linear ST with Pacejka slip dynamics**: the understeer scalar K
  already captures the steady-state contribution; the marginal complexity
  didn't fit the budget.
- **Higher-order velocity terms** for the >30 m/s residual.
- **Per-turn-direction coefficients** for the small left/right asymmetry.
