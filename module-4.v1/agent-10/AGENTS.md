# AGENTS.md — Module 4 v1 (closed-loop tree search on top of m3 + V1 baseline)

You are working on the lateral-fidelity challenge. The two KPIs to minimise
are in your task prompt: pooled yaw-rate RMSE and distance-resampled
cross-track-error RMSE. Your job in m4.v1 is **not** to fit better
coefficients to one model — it is to **run a structured search across
multiple candidate models**, with the verifier in the loop, the test split
frozen, and structural diversity enforced.

This template inherits everything from m3.v2 + m3.v3 (the V1 baseline, the
`models/` first-class object pattern, the skills toolkit) and adds five
mechanisms that close the loop. They are listed in [`references/closing-the-loop.md`](references/closing-the-loop.md);
the picture at the bottom of that doc is the spine you're operating on.

## Operating contract — what your `predict()` will see at grading time

The canonical grader hands your `predict(sim_df, platform)` a DataFrame
containing **only these eight input columns**:

| column | meaning |
|---|---|
| `t_s` | sample time (s) |
| `delta_wheel_deg` | hand-wheel angle (deg) |
| `delta_road_rad` | road-wheel angle (rad) — the steering channel to use in physics models |
| `v_mps` | vehicle speed (m/s) |
| `a_long_mps2` | longitudinal acceleration (m/s²) |
| `accel_pedal_pct` | accelerator pedal position (%) |
| `brake_pressed` | brake-pressed flag (0/1) |
| `yaw_rate_pred_rads` | V0 baseline yaw rate (rad/s) — V1 already uses this; you can too |

**Anything else will raise `KeyError`.** Notable absences:

- `yaw_rate_meas_rads` — the truth channel. Denied (it's what the grader scores against).
- `a_lat_meas_mps2` — denied; in this dataset it's computed kinematically from truth yaw rate. **Always substitute an allowlist proxy** (e.g. `v_mps * yaw_rate_pred_rads`).
- `yaw_rate_resid_rads`, `a_y_resid_mps2`, `x_m`, `y_m`, `psi_rad` — denied (direct or integrated truth leaks).

The local `data/` tree contains three views of the same segments:

- **`data/sim-only/segments/`** — agent-facing input view. Only the 8
  allowlist columns. The local `score-model` skill and `pre-flight-final-model`
  use this for the dry-run.
- **`data/sim/segments/`** — full-fidelity view including truth. Used for
  *offline* fitting by `fit-model` and for the CV folds in `score_cv`.
- **`data/sim-only/test/` and `data/sim/test/`** — **frozen test split**.
  Refused by `score-model` and `score_cv` unless invoked with `final=True`.
  Only `pre-flight-final-model --final` reads it. See § "Test-split discipline".

Tesla has no `yaw_rate_meas_rads` channel — V0 passthrough is the honest
fallback. Don't fit Tesla.

## What V1 is, and why m4 starts above it

`code/v1_baseline.py` is the converged rung-0 model from the m3.v3 cohort:
kinematic single-track + understeer + first-order lag + platform-gated
per-segment δ₀. V1's pooled-dev scores are constants of record:
**yaw RMSE = 0.005874 rad/s, CTE RMSE = 56.81 m** (vs V0: 0.01293 / 163.83).

m4's job is not to refit V1. It is to **build candidate models that attack
V1's residual structurally**, score them under CV, and pick the dev-winner.

## Working directory layout

```
m4.v1/
├── AGENTS.md            (this file)
├── README.md
├── MODELS.md            ← registry; auto-appended by skills/iterate/
├── TREE.json            ← search tree; auto-appended by skills/iterate/
├── EXPERIMENTS.md       ← log; auto-appended by skills/iterate/
├── models/              ← one subdir per candidate
│   └── <name>/
│       ├── predict.py
│       ├── notes.md     ← rung, parent, expected residual character
│       └── assessment.md
├── final-model/         ← where you ship the chosen model
├── skills/
│   ├── iterate/                  ← NEW in m4: one-shot inner-loop step
│   ├── critique-residuals/       ← NEW in m4: typed-grounded router
│   ├── visualise-tree/           ← NEW in m4: render TREE.json
│   ├── assess-candidate-model/   ← inherited from m3.v3
│   ├── score-model/   + cv.py    ← m4: k-fold route-grouped CV wrapper
│   ├── fit-model/, compare-models/, inspect-residuals/, residual-structure/,
│   │   route-bias/, visualise-segment/, make-train-dev-split/, load-segments/,
│   │   pre-flight-final-model/   ← all inherited
├── references/
│   ├── m4-cohort-findings.md     ← NEW: 8 evidence-backed cohort patterns
│   ├── closing-the-loop.md       ← NEW: how the 5 m4 mechanisms compose
│   └── anti-patterns.md, approach-menu.md, dynamics-formulations.md,
│       two-kpi-tradeoff.md, ceiling-moves.md, exploration-discipline.md
├── _shared/
│   ├── rung1_starter.py          ← NEW: dynamic ST scaffold (RK4 + fit C_α, Iz)
│   └── (cte math, trajectory helpers — inherited)
├── launch-rungs/                 ← NEW: parallel divergent subagent manifest
│   ├── manifest.yaml
│   ├── launch.sh
│   └── README.md
└── rpi/                          ← NEW: hard-locked Research → Plan → Implement
    ├── run-research.sh
    ├── run-plan.sh
    ├── run-implement.sh
    ├── lock.sh
    └── templates/
```

## The five m4 mechanisms

Read [`references/closing-the-loop.md`](references/closing-the-loop.md)
for how these compose. In one paragraph:

1. **`skills/iterate/`** — every candidate model goes through one tool call.
   Runs the verifier gate (k-fold route-grouped CV, residual structure, fit
   diagnostics, gap-to-parent, gap-to-V1), appends to `TREE.json` and
   `MODELS.md`, returns a routing string from `critique-residuals`.
2. **`skills/score-model/cv.py` + test-split refusal** — dev scoring uses
   5-fold route-grouped CV (mean ± σ); test split is denied except in
   `pre-flight --final`.
3. **`rpi/`** — three-phase hard-locked Research → Plan → Implement.
   RESEARCH.md and PLAN.md are chmod-locked between phases. Use when the
   task wants a rung-1 attempt that needs a fresh-context decision.
4. **`launch-rungs/`** — parallel divergent subagents, each constrained to a
   different rung. Orchestrator picks the dev-CV winner.
5. **Stagnation reset** — when `iterate` returns `stagnation: True`
   (3 consecutive warn/fail nodes), start a fresh session with only
   `EXPERIMENTS.md`, `TREE.json`, and the current leader in context.

## The highest-leverage moves on this dataset

Read [`references/m4-cohort-findings.md`](references/m4-cohort-findings.md)
**first** — it leads with the four evidence-backed cohort moves (per-platform
bias correction, orthogonal residual learner head, fit-C_α-and-Iz rung-1,
route-grouped CV) ordered by what the m3.v3 cohort actually shipped that won.
Orthogonal is a peer of rung-1, not a fallback. The historically-winning pair
on this dataset is `(per-platform bias correction) + (residual-learner head)`.

## Test-split discipline (do not break this)

The frozen test split exists to give you an honest stopping signal under the
m4 closed-loop iteration count. **`score-model` and `score_cv` refuse to
read it** outside of `pre-flight-final-model --final`. The discipline:

- Iterate against dev (CV mean ± σ) as many times as you want.
- Run `pre-flight --final` once, at the end.
- If `dev / test gap > 5%` on either KPI, the preflight warns. Treat the warning
  as the canonical overfit signal — usually means the cohort §6 pattern hit
  (a lever overfits a route group).

## The default workflow — mechanisms are on by default

Cohort evidence (m3.v2, m3.v3) is unambiguous: optional disciplines get
skipped under time pressure. The default loop **invokes** the m4 mechanisms;
opting out is the explicit, documented exception.

### Always mandatory (no opt-out)

- `skills/iterate/` on every candidate — only path into `MODELS.md` / `TREE.json`.
- Route-grouped k-fold CV — `score_cv` is what iterate calls internally.
- Test-split refusal — `score-model` raises `TestSplitDeniedError` outside `--final`.
- `pre-flight-final-model --final` at the end.
- `notes.md` `## What this differs from` section — iterate refuses bundles without it.

### Default + documented opt-out

- **RPI phase separation** (`bash rpi/run-research.sh`) — default ON for any
  task budget > 30 min OR where the plan considers a rung-1 attempt. Skip
  only for short refinement-only runs where you already know the candidate
  shape; document the skip in `REPORT.md`.
- **`launch-rungs/`** (fan-out to parallel rung subagents) — default ON when
  the plan names a rung-1 climb AND your environment supports parallel
  Claude Code sessions. Skip when running solo on limited wall clock;
  document the skip.
- **Stagnation reset** — fires automatically when `iterate` flags
  `stagnation: True`. The reset itself is mechanical (verdict is capped at
  `keep`, can't be promoted), but you should also open a fresh session.

### A workable inner-loop with the defaults

1. **Read the V1 score** (V1's numbers are constants — don't re-score V1).
   Run `skills/score-model` and `residual-structure` on V1 to see *which*
   residual you're attacking and on which platform.
2. **Run `bash rpi/run-research.sh`** to write a RESEARCH.md naming ≥5
   alternatives. The script cold-starts a fresh Claude Code session if
   `claude` is on PATH (see `rpi/README.md` for the fallback).
3. **Run `bash rpi/run-plan.sh`** — fresh session, reads only RESEARCH.md +
   cited references. Outputs PLAN.md naming 2 candidates (one rung-0
   refinement + one structurally-different — orthogonal or rung-1).
4. **Run `bash rpi/run-implement.sh`** — for each candidate, create
   `models/<name>/` with `notes.md` (including the mandatory
   `## What this differs from` section), then `predict.py`. Run
   `skills/iterate/iterate` on the bundle.
5. **If your environment supports parallel sessions**, instead of step 4 use
   `bash launch-rungs/launch.sh` (or [`launch-rungs/orchestrate.md`](launch-rungs/orchestrate.md)
   from inside Claude Code) to fan out 4 rung-constrained subagents. The
   orchestrator runs iterate on each return.
6. **Follow the route** from `critique-residuals` unless you have a reason
   not to. The cohort-evidenced default is `try_residual_learner`
   (orthogonal) when V1's physics levers are at noise floor.
7. **Render the tree** every 5 iterations with `skills/visualise-tree/` —
   spot rung-0 collapse or branch stagnation visually.
8. **Before declaring done**: run `pre-flight-final-model --final`. Reads
   the frozen test split for the first time; reports dev/test gap.

### Opting out of a default — the deviation contract

If you skip RPI or launch-rungs, write one sentence in `REPORT.md` § "Process
deviations" naming what you skipped and why. The cohort wants to see the
deviation so the next template iteration can learn from it.

## Before declaring done — deliverable hygiene checklist

1. `pre-flight-final-model --final` passes every check.
2. `MODELS.md` has ≥4 entries with ≥1 tagged `rung: 1+` or `rung: orthogonal`.
3. `TREE.json` shows ≥2 distinct rung values (catches rung-0 collapse).
4. If you ran RPI: `rpi/artifacts/RESEARCH.md` and `PLAN.md` are locked
   (preflight verifies non-writable).
5. `final-model/predict.py` is the dev-CV winner per `iterate` history.
6. `REPORT.md` cites the structures you ruled out + why.
7. The dev/test gap from preflight is within band.

If any check fails, fix and re-run. Don't ship a bundle that doesn't pass.

## Working with skills and references

Skills and references are **clay, not library**. Output not useful? Open
the body, add the column or condition you need, save, re-run. The cohort
ratchets through this — your edits feed the next cohort's template.
