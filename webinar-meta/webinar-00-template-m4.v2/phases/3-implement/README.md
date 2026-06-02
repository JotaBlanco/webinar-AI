# Phase 3 — Implement

You are in the **Implement** phase. Outputs: candidate bundles under
`phases/3-implement/models/<name>/`, registry updates to `MODELS.md` /
`TREE.json` / `EXPERIMENTS.md` (auto-written by `skills/iterate/`), and
finally a `final-model/` bundle at the template root.

## Goal

Build the two candidates from `PLAN.md`, score them through the closed-loop
verifier gate, pick the dev-CV winner, and ship.

## Scope boundary

You may read:

- `phases/2-plan/artifacts/PLAN.md` — the locked Phase 2 artifact. This is
  your spec.
- `skills/*/` — all skill bodies, freely.
- `_shared/` — the rung-1 starter and CTE math.
- `references/` — only when implementing a candidate whose `PLAN.md` entry
  names a specific reference. Don't browse — load the named ones.
- `phases/1-research/artifacts/RESEARCH.md` — readable but not needed; the
  plan summarizes what matters.

You may write:

- `phases/3-implement/models/<name>/predict.py`, `notes.md`, etc.
- `final-model/` (the deliverable bundle at the template root)
- `MODELS.md`, `TREE.json`, `EXPERIMENTS.md` — but only through
  `skills/iterate/`. Do not edit them by hand.
- `REPORT.md` at the template root, at the end.

You may **not**:

- Edit `RESEARCH.md` or `PLAN.md` (they're chmod-locked anyway).
- Add candidates not named in `PLAN.md`. If iterate routes you toward a
  third candidate, that's a stagnation-reset signal, not an invitation to
  expand the plan.

## Where candidates live in v2 — pathing note

In v2 candidate models live under `phases/3-implement/models/<name>/`, NOT
at the template root (v1 has them at root). Two ways to invoke
`skills/iterate/`:

1. **`cd phases/3-implement/`** before invoking iterate, so its default
   `models/<name>/` path resolves to `phases/3-implement/models/<name>/`.
2. **Pass an explicit `model_dir`**: `iterate("phases/3-implement/models/<name>")`
   from the template root.

The registries (`MODELS.md`, `TREE.json`, `EXPERIMENTS.md`) live at the
template root in both v1 and v2 so they remain readable when this phase
needs to compact to a fresh session.

## The inner-loop recipe

This is the canonical m4 inner loop. Both PLAN.md candidates go through it.

1. **Build the candidate skeleton.** Create
   `phases/3-implement/models/<name>/` with:
   - `notes.md` — rung, parent, expected residual character, one-paragraph
     formulation summary copied from PLAN.md.
   - `predict.py` — the candidate's `predict(sim_df, platform)` function.
   - If a rung-1 candidate: copy `_shared/rung1_starter.py` as a starting
     point and **fit `C_αf`, `C_αr`, `Iz` per platform** (non-negotiable —
     cohort §1+§7).
   - If a rung-0 candidate that needs offline fitting, run `skills/fit-model/`
     against `data/sim/` and ship `coeffs.json` next to `predict.py`.

2. **Run `skills/iterate/` on the bundle.** This is the only place that
   writes to the registries. The skill runs:
   - 5-fold route-grouped CV via `skills/score-model/cv.py` (mean ± σ).
   - `residual-structure` diagnosis.
   - Fit diagnostics + gap-to-parent + gap-to-V1.
   - `critique-residuals` for a typed-grounded routing string.
   - Appends a node to `TREE.json`, a row to `MODELS.md`, an entry to
     `EXPERIMENTS.md`.

3. **Follow the route** that `critique-residuals` emits, unless you have
   a documented reason not to. Routes are typed and verifiable:
   `try_residual_learner`, `add_platform_bias`, `escalate_rung`,
   `compact_and_restart`, `accept_as_leader`, etc.

4. **Render the tree** every few iterations with `skills/visualise-tree/`
   to spot rung collapse or branch stagnation visually.

5. **Pick the dev-CV winner** once both PLAN.md candidates have at least
   one `iterate` node. The winner's `predict.py` gets copied to
   `final-model/predict.py`.

6. **Run `skills/pre-flight-final-model/ --final`** at the very end. This
   is the only place the frozen test split is read.

## Do not manually score candidates

Every score that doesn't pass through `iterate` is a silent un-logged node.
The cohort failure mode is silently re-converging on the same approach
because half the attempts weren't logged. If you need a raw score for a
half-built `predict.py`, call `score-model` directly — but the moment you
have a candidate you'd consider promoting, run `iterate` on it.

## launch-rungs — when to fan out

`launch-rungs/launch.sh` is invoked **inside this phase**, after `PLAN.md`
is locked. The plan becomes the manifest source: each subagent gets one of
the named candidates plus a rung constraint matching its entry in the plan.

Use it when:

- Your wall clock allows ≥2 sessions in parallel.
- The two PLAN.md candidates are structurally distant enough that running
  them sequentially in one context would mean significant cross-pollination.

Skip it when:

- You only have one session of compute.
- The candidates are tight variants where the second one will benefit from
  iteration learnings on the first.

See [`../../launch-rungs/README.md`](../../launch-rungs/README.md) for the
mechanics. In sequential mode the structural-diversity guarantee still
holds because PLAN.md mechanically enforces it.

## The stagnation reset

When `iterate` returns `stagnation: True` (3 consecutive warn/fail nodes
on the same branch), don't push through. The recommended next move is to:

1. Compact this session.
2. Open a **fresh Claude Code session** in the template root.
3. Seed it with **only**:
   - `EXPERIMENTS.md` (the log)
   - `TREE.json` (the tree)
   - The current leader's `predict.py` (`final-model/predict.py` if you've
     already promoted one, else the dev-CV-leading entry from `MODELS.md`)
   - `PLAN.md` (the spec — re-read what was supposed to happen)
   - This phase README

4. Decide whether to revise the parent of the next iterate call or accept
   the leader.

This is the v1 "stagnation reset" mechanism. The phase boundary discipline
makes the reset cheap: registries persist at template root and seed the
fresh session.

## Test-split discipline (do not break this)

The frozen test split (`data/sim-only/test/` and `data/sim/test/`) is
refused by `score-model` and `score_cv` outside of `pre-flight-final-model
--final`. The discipline:

- Iterate against dev CV (mean ± σ) as many times as you want.
- Run `pre-flight --final` once, at the end.
- If `dev / test gap > 5%` on either KPI, the preflight warns. Treat the
  warning as the canonical overfit signal — usually it means a lever
  overfits a route group (cohort §6).

## Before declaring done — hygiene checklist

1. `pre-flight-final-model --final` passes every check.
2. `MODELS.md` has ≥4 entries with ≥1 tagged `rung: 1+` or `rung: orthogonal`.
3. `TREE.json` shows ≥2 distinct rung values.
4. `phases/1-research/artifacts/RESEARCH.md` and
   `phases/2-plan/artifacts/PLAN.md` are both locked (preflight verifies).
5. `final-model/predict.py` is the dev-CV winner per `iterate` history.
6. `REPORT.md` at the template root cites the structures you ruled out + why.
7. Dev/test gap from preflight is within band.

If any check fails, fix and re-run. Don't ship a bundle that doesn't pass.

## Exit ritual

```bash
# from template root
uv run python -m skills.pre_flight_final_model.preflight --final
# fix anything it flags, then write/update REPORT.md and you're done.
```
