# Task — idea-01 lateral fidelity (m4.v2.01)

We have a kinematic single-track vehicle model that takes measured steering
angle and velocity as inputs and predicts lateral behaviour — yaw rate, and
the trajectory (x, y, heading) that follows by integration.

Baseline (V0) is in `code/ks_model.py`; its predictions are pre-computed as
`yaw_rate_pred_rads` in every `sim.csv`, alongside the truth channel
`yaw_rate_meas_rads`. The current cohort leader (V1, m3.v3 converged
rung-0 model) lives at `code/v1_baseline.py`: pooled-dev
**yaw RMSE = 0.005874 rad/s, CTE RMSE = 56.81 m**.

You'll be graded on:
  1. Yaw-rate RMSE (rad/s)
  2. Distance-resampled cross-track-error RMSE (m) — your trajectory vs
     truth, sampled at uniform distance.

## What's new in v2.01 vs v2

The last four cohorts (m3.v2, m3.v3, m4.v1, m4.v2 — **90 agents**) all
plateau at yaw ≈ +57% / CTE ≈ +72%. Every winner sits in rung 0 (kinematic
+ understeer tweaks + residual ridge). **Zero agents shipped a rung-1 model**
in 90 attempts. The dynamics ladder has never been climbed.

v2.01 prepopulates the tree with **five working physics models** sitting at
rung 1, rung 2, rung 3, and one orthogonal formulation. They are not
sketches: each ships with runnable `model.py`, `fit.py`, `eval.py`,
`validate.py`, initial `coeffs.json` from `carParams`, and a README. You
can run all five on dev within the first 20 minutes and iterate on whichever
beats V1.

The five models live under `phases/3-implement/models/`:

| dir | model | rung | targets |
|---|---|---|---|
| `m1-linear-dynamic-st/`    | Linear dynamic single-track            | 1          | transient regime, phase lag |
| `m2-fiala-tire-st/`        | Nonlinear (Fiala) tire on M1           | 2          | high-`a_lat` saturation |
| `m3-double-track-load-transfer/` | Double-track + lateral load transfer | 3          | F150 ceiling, heavy-vehicle asymmetry |
| `m4-relaxation-length/`    | Relaxation-length tire on kinematic    | orthogonal | distance-based phase lag |
| `m5-friction-circle/`      | M1 + long/lat friction-circle coupling | 3          | brake-in-corner, accel-out |

Each model README explains the equations, parameters, what residual symptom
should make you reach for it, and what failure mode to watch for.
`references/dynamics-formulations.md` has the long-form derivations.

## Time budget — 90 minutes, soft

You self-pace, but here's a balanced spend that uses what's prefilled:

| Block | Minutes | What |
|---|---|---|
| **0. Triage** | 15 | Read `phases/1-research/README.md`. Run `score-model` on V1 baseline against dev. Use the new `diagnose-by-physics-regime` skill to see where the residual concentrates (transient / saturation / load-transfer / phase-lag / coupling regimes). |
| **1. Run prefilled baselines** | 20 | `cd phases/3-implement/models/<model>/ && python fit.py && python eval.py` for each of the 5. Capture pooled yaw/CTE per platform per model. |
| **2. Pick top 2 and iterate** | 40 | Promote the 2 best to leaders; use `skills/iterate` to spawn variants. Allowed to combine (e.g. M1 + relaxation-length term from M4). |
| **3. Validate + report** | 15 | `skills/pre-flight-final-model --final` against the frozen held-out split (`references/held-out-split.md`). Write REPORT.md. |

Hard rule: **at least one of the candidates you log in `MODELS.md` must be
rung ≥ 1**. This is gated by `pre-flight-final-model`. The 90-agent priors
make it very likely the winner is also rung ≥ 1, but the gate is on
*attempting* the climb, not on it winning.

## Ship at `final-model/`

  - `predict.py` exporting `predict(sim_df, platform) -> DataFrame` aligned
    with `sim_df.index`: `yaw_rate_pred_rads` required; `x_m, y_m` optional
    (integrated from yaw_rate + measured v if omitted).
  - `manifest.json` with `platform_support` and `predict_callable`
    (e.g. `"predict.py:predict"`).
  - Any coeffs/scripts your predict depends on.

## Known ceiling — read before chasing F150

`references/f150-yaw-ceiling.md` documents the per-platform plateau every
cohort has hit. F150 yaw sits flat at **~+21%** across all 90 agents in all
modules. This is almost certainly a heavy-vehicle / load-transfer physics
issue (which is exactly why M3 is prefilled). Don't burn budget on F150 with
rung-0 tweaks.
