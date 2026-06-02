# AGENTS.md — Module 4 v2.01 (RPI-first + prefilled physics ladder)

You are operating an **RPI-first** template. The Research → Plan → Implement
lifecycle is the spine: every action belongs to a phase, every phase reads
only what the prior phase produced. Start at
[`phases/1-research/README.md`](phases/1-research/README.md). This root file
is an index, not a guide — the load-bearing guidance lives in the per-phase
READMEs.

**New in v2.01:** five physics models are prefilled at
`phases/3-implement/models/` (rungs 1, 2, 3, orthogonal). They are
runnable on day one. See `TASK.md` § "What's new in v2.01" for the full
list and the 90-minute budget.

## Operating contract — what your `predict()` will see at grading time

The canonical grader hands `predict(sim_df, platform)` a DataFrame with
**only these eight input columns**: `t_s`, `delta_wheel_deg`,
`delta_road_rad`, `v_mps`, `a_long_mps2`, `accel_pedal_pct`, `brake_pressed`,
`yaw_rate_pred_rads`. Anything else raises `KeyError`. Notable denied
columns: `yaw_rate_meas_rads` (truth), `a_lat_meas_mps2` (computed from
truth — substitute `v_mps * yaw_rate_pred_rads` or similar), and the
residual / pose channels (`x_m`, `y_m`, `psi_rad`, `*_resid_*`).

The local `data/` tree:

- `data/sim-only/segments/` — agent-facing view (8 allowlist columns).
- `data/sim/segments/` — full-fidelity view with truth. Offline fits only;
  your `predict()` must not depend on it.
- `data/sim-only/test/` and `data/sim/test/` — **frozen test split**.
  Refused by `score-model` and `score_cv` unless `final=True`, which is
  only allowed from `pre-flight-final-model --final`.

Tesla has no truth — V0 passthrough is the honest fallback. Don't fit Tesla.

## V1 baseline — the floor

`code/v1_baseline.py` is the m3.v3 cohort's converged rung-0 model.
Pooled-dev: **yaw RMSE = 0.005874 rad/s, CTE RMSE = 56.81 m**. Constants
of record — **don't refit V1**. m4's job is to beat V1 structurally.

## Layout

```
m4.v2/
├── AGENTS.md            (this file — index only)
├── README.md            human-facing thesis
├── MODELS.md / TREE.json / EXPERIMENTS.md   ← shared registries; auto-filled by skills/iterate
├── phases/
│   ├── 1-research/      README.md + run.sh + PROMPT.md + artifacts/RESEARCH.md
│   ├── 2-plan/          README.md + run.sh + PROMPT.md + artifacts/PLAN.md
│   └── 3-implement/     README.md + run.sh + PROMPT.md + models/<candidate>/
├── lock.sh              chmod -w helper used by all three phases
├── launch-rungs/        invoked INSIDE phase 3 (after PLAN.md is locked)
├── skills/, references/, _shared/, code/, data/, final-model/, pyproject.toml
```

Candidate models live under `phases/3-implement/models/<name>/`, NOT at the
template root. When you invoke `skills/iterate/`, either `cd phases/3-implement/`
first or pass an explicit `model_dir` path under `phases/3-implement/models/`.
The registry files (`MODELS.md`, `TREE.json`, `EXPERIMENTS.md`) stay at root
so they remain readable when a phase compacts to a fresh session.

### Prefilled candidates (v2.01)

`phases/3-implement/models/` ships with five fully-runnable physics
candidates. Each has `model.py`, `fit.py`, `eval.py`, `validate.py`,
`coeffs.json` (initial guess from `code/parameters.py`), `notes.md`, and
`README.md`. Run `python fit.py && python eval.py` from any of them to
see a working scorecard. The `MODELS.md` / `TREE.json` registries are
prepopulated with these as `status: drafting` children of V1.

| dir | model | rung |
|---|---|---|
| `m1-linear-dynamic-st/`          | Linear dynamic single-track     | 1 |
| `m2-fiala-tire-st/`              | Fiala nonlinear tire on M1      | 2 |
| `m3-double-track-load-transfer/` | Double-track + lateral load transfer | 3 |
| `m4-relaxation-length/`          | Distance-based tire relaxation  | orthogonal |
| `m5-friction-circle/`            | M1 + long/lat friction coupling | 3 |

You may take any of these, fit it, log it via `iterate`, branch off, or
shelve it. The pre-flight gate enforces ≥1 entry tagged `rung ≥ 1` —
which all five satisfy if logged.

## The lifecycle

1. **Phase 1 — Research.** Read [`phases/1-research/README.md`](phases/1-research/README.md).
   Diagnose V1's residual, list candidates, output `RESEARCH.md`. No code.
2. **Phase 2 — Plan.** Read [`phases/2-plan/README.md`](phases/2-plan/README.md).
   Fresh context. Reads only `RESEARCH.md`. Picks 2 candidates by default
   (one rung-0, one structurally-different); up to 3 with rationale.
   Outputs `PLAN.md`.
3. **Phase 3 — Implement.** Read [`phases/3-implement/README.md`](phases/3-implement/README.md).
   Fresh context. Reads only `PLAN.md` + skills. Builds, iterates, ships.

Each phase ends by chmod-locking its artifact (`bash lock.sh <path>`).
The lock is mechanical — `pre-flight-final-model` rejects the bundle if
either artifact is writable.

## The 5 mechanisms — which phase owns each

| mechanism | phase | role |
|---|---|---|
| typed-grounded critique router (`skills/critique-residuals`) | 2 (planning) + 3 (routing) | informs candidate choice; routes after each iterate call |
| tree-search planning | 2 | two-candidates rule produces a planted tree of two children of V1 |
| `skills/iterate/` (verifier gate) | 3 | only skill that writes MODELS.md / TREE.json |
| `launch-rungs/` parallel subagents | 3 | optional fan-out using PLAN.md as the manifest |
| stagnation reset | 3 | iterate flags it → agent compacts to fresh session, seeded with `EXPERIMENTS.md` + `TREE.json` + leader |

Phase 1 owns no mechanism — it is the open-context diagnostic phase.

## Before declaring done — hygiene checklist

Run from `phases/3-implement/` at the very end:

1. `pre-flight-final-model --final` passes every check.
2. `MODELS.md` has ≥4 entries with ≥1 tagged `rung: 1+` or `rung: orthogonal`.
3. `TREE.json` shows ≥2 distinct rung values.
4. `phases/1-research/artifacts/RESEARCH.md` and `phases/2-plan/artifacts/PLAN.md`
   are both locked (preflight verifies non-writable).
5. `final-model/predict.py` is the dev-CV winner per the iterate history.
6. `REPORT.md` cites the structures you ruled out + why.
7. The dev/test gap from preflight is within band.

## Skills and references are clay

Skill output not useful? Open the body, add what you need, save, re-run.
Same for references. The discipline you owe the template is the phase
boundary, not skill purity.
