# Lateral fidelity — attribution of model upgrades to KS

Speed-known lateral-only contract honoured throughout: every variant runs with
`v_meas` and `delta_road_rad` clamped from the rlog. The residual under test is
the **lateral model lie** (`yaw_rate_pred - yaw_rate_meas`), in rad/s.

## 1. Segments

All four available Ford segments are used as a single common pool (Tesla
excluded — no decodable yaw-rate truth):

| short id | platform | dur [s] | v [m/s] min/max | `yaw_meas_rms` [rad/s] |
|---|---|---|---|---|
| MachE/08ec7b9a/1   | FORD_MUSTANG_MACH_E_MK1  | 57.9 |  4.6 / 11.1 | 0.0145 |
| MachE/112bd787/12  | FORD_MUSTANG_MACH_E_MK1  | 57.9 |  0.0 / 20.2 | 0.0060 |
| F150/0b2c0bec/34   | FORD_F_150_LIGHTNING_MK1 | 57.9 | 26.4 / 35.9 | 0.0188 |
| F150/112e4d6e/9    | FORD_F_150_LIGHTNING_MK1 | 57.9 |  0.0 / 19.0 | 0.0926 |

The pool spans a useful operating envelope: highway cruise (F150/34, ~32 m/s,
gentle curvature) and the low-speed transient regime (F150/9, parking-lot
manoeuvres, `delta_meas_rms` ~0.09 rad).

## 2. Regime definition

A sample is labelled by *what the car is doing right now*, using two physical
thresholds:

| Regime | Condition |
|---|---|
| `straight`  | abs(yaw_meas - bias) < 0.02 rad/s  (~1.1 deg/s; effectively not turning) |
| `transient` | abs(d delta /dt) > 0.05 rad/s AND not straight (driver actively moving the wheel) |
| `steady`    | everything else (turning, hand settled) |

The 0.02 rad/s yaw-rate cut separates "barely-perturbed straight" from any
actual cornering at the lowest speeds in our pool (at v=5 m/s, yaw=0.02 rad/s
implies turning radius R >= 250 m — clearly straight). The 0.05 rad/s
d(delta)/dt cut is roughly the slowest "deliberate steering input"; slower
than that counts as steady-state regulation. Same thresholds across all
variants.

## 3. Variants

Ordered list of incremental upgrades. Each one plugs a *named* deficiency of
the previous variant. Same four segments, same regime mask, same bias term
once it is introduced.

- **v0 — Baseline KS (`yaw_rate_pred_rads` from sim.csv).** Vanilla
  `(v/L) * tan(delta)`. No tyre, no slip.
- **v1 — KS + per-segment yaw-rate bias.** Plugs the *sensor / road-camber
  bias*. Estimated from each segment's own near-straight samples
  (abs(delta) < 1e-3 rad AND abs(a_y_meas) < 0.2). Estimates:
  MachE/08ec7b9a/1 `+0.01364`, MachE/112bd787/12 `-0.00080`,
  F150/0b2c0bec/34 `-0.01195`, F150/112e4d6e/9 `-0.00521` rad/s. These are
  real — the F150 highway segment is driving down a road with -0.012 rad/s of
  "perceived" yaw at the wheel-zero, almost certainly road crown / cant.
- **v2 — Linear single-track with openpilot-canonical Calpha.** Plugs the
  *no-slip lie*: tyres develop a slip angle proportional to lateral force, so
  steady-state yaw gain drops with speed. Implemented as the 2-state
  `(v_y, yaw)` linear bicycle, RK4-integrated with adaptive sub-stepping (the
  fastest mode `(C_f+C_r)/(m*v)` becomes stiff below v = 5 m/s). At v < 1.5
  m/s we fall back to KS (the bicycle is singular at zero speed).
- **v3 — Linear ST with fitted Calpha (front/rear scale).** Plugs the
  *wrong-prior lie*: the production Calpha is loaded-curb tyre stiffness, but
  actual pavement / temperature / inflation / true axle load can swing it ~30
  pct. Nelder-Mead on summed squared yaw-rate residual converged to
  `(scale_f, scale_r) = (0.633, 1.612)` — softer front, stiffer rear than the
  prior, consistent with mild understeer trim and the F150's load distribution
  shifting the rear axle off its stiff-tyre regime.
- **v4 — Variant 3 + small data-driven residual learner.** Plugs whatever the
  linear-tyre bicycle still misses (mild lag, non-linear tyre at higher abs(a_y),
  geometry that isn't fully captured). Ridge-regularised linear regression on
  `[1, delta, delta*v, a_y_pred, d(delta)/dt]`. Coefficients (rad/s per unit
  feature): `bias = -1.98e-3`, `delta = -9.1e-4`, `delta*v = +1.18e-2`,
  `a_y_pred = -4.87e-3`, `d(delta)/dt = -1.23e-2`. The `delta*v` and
  `d(delta)/dt` terms dominate — the bicycle is slightly *over*-damping the
  transient and slightly *under*-predicting the speed-scaling of yaw gain.

## 4. Attribution table

All RMSEs in rad/s. `pct_variance_closed = 1 - var(resid_this) / var(resid_baseline)`.

| variant | RMSE_overall | RMSE_straight | RMSE_steady | RMSE_transient | Delta_overall_vs_prev | pct_variance_closed |
|---|---:|---:|---:|---:|---:|---:|
| v0_baseline_KS                | 0.01499 | 0.01422 | 0.01842 | 0.02439 |  +0.00000 |   0.00 % |
| v1_KS_plus_yaw_bias           | 0.00909 | 0.00754 | 0.02211 | 0.01996 |  -0.00590 |  65.98 % |
| v2_LinearST_prior_Calpha      | 0.00578 | 0.00494 | 0.01348 | 0.01136 |  -0.00331 |  87.45 % |
| v3_LinearST_fit_Calpha        | 0.00418 | 0.00375 | 0.00796 | 0.00868 |  -0.00160 |  93.16 % |
| v4_ST_plus_residual_learner   | 0.00356 | 0.00322 | 0.00735 | 0.00547 |  -0.00062 |  93.69 % |

The straight-regime RMSE on v1 actually *worsens* slightly in `steady` and
`transient` columns relative to baseline (0.018 -> 0.022 and 0.024 -> 0.020) —
subtracting the bias re-aligns the "true" zero of yaw rate and exposes the
cornering lie that KS was previously coincidentally cancelling against the
bias on those segments. v2 cleans that up.

## 5. Figure

`report.png` overlays measured yaw_dot (bias-corrected) against v0 / v2 / v3 /
v4 predictions on **F150/0b2c0bec/34** — the highest-speed segment in the
pool, which also has the largest absolute swings in yaw_dot (transient
content). At 30 m/s, the same delta produces 6x the lateral force as at 5 m/s;
tyre slip is visibly in play, and the KS-vs-ST gap is most obvious there.

## 6. Reproduce

```bash
# from this folder
python3 tools/lateral_fidelity.py
```

Produces `report.png` here and writes intermediate numbers to
`tools/results.json`. Pure stdlib + numpy + scipy + pandas + matplotlib.

## Missing information

The prompt referenced `/Users/javiquix/Desktop/quixdev/webinar-AI/.venv` for
execution; that virtual environment does not actually exist in the sandbox.
System `python3` (Homebrew 3.13) already has numpy, scipy, pandas, and
matplotlib, so the work proceeded with `python3` directly. No package
substitutions were needed for the deliverable; pycapnp / cantools / zstandard
were not invoked because the work is downstream of `generate_simdata_ford.py`
and consumes the already-decoded sim.csv files.

## Narrative

The biggest *single* contribution comes from variant **v2 — adding linear
tyre slip via the single-track bicycle (KS -> ST)** at the openpilot-canonical
Calpha prior: RMSE goes from 0.00909 -> 0.00578 rad/s, with the bulk of the
win in the **transient** regime (0.020 -> 0.011 rad/s). This is the physics
step that plugs the largest model lie: KS asserts that the car's velocity
vector is always parallel to its front wheel, which is *wrong by an order
`m * a_y / C_alpha` slip-angle correction* under any non-trivial lateral
force. At F150/34's highway speeds that correction is the dominant residual,
and the bicycle's `1 / (1 + K * v^2)` gain-rolloff captures it. The yaw-bias
step (v1) is a larger *number*, but it's plugging an instrumentation lie, not
a vehicle-dynamics lie — strictly, it cleans up the truth signal, not the
model. The fitted-Calpha step (v3) recovers a further 6 percentage points of
variance by acknowledging that "manufacturer brochure" tyre stiffness is a
starting point, not the truth. The residual learner (v4) only finds 0.6 pp
of variance left — a good sign that the linear bicycle is doing essentially
all of the physics the data wants it to do.
