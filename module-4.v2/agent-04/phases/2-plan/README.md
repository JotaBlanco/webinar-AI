# Phase 2 — Plan

You are in the **Plan** phase. Output: `phases/2-plan/artifacts/PLAN.md`.

## Goal

Down-select from `RESEARCH.md` to 2 candidates by default — **one rung-0
refinement and one structurally-different candidate (rung 1+ OR orthogonal
— peer rank)**. Up to 3 candidates if RESEARCH.md justifies it (see § "The
candidates rule" below). Specify each in enough detail that Phase 3 can
build them without re-deciding anything.

## Why this phase exists — the fresh-context bet

The Plan phase runs in a fresh Claude Code session deliberately. Empirical
basis:

- CMU 2026 (test-time-scaling ceiling paper): model self-selection only
  closes ~55% of the oracle gap when sample count is small; the gap
  *widens* with N. The Plan-phase fresh start gives you a sharp decision
  while N is still small.
- Horthy / HumanLayer 100K-session telemetry: the "smart zone" cliff is at
  ~40% context fill on 200k models. Phase 1 will have spent budget on
  candidate enumeration; the Plan decision is the high-stakes one and
  deserves a clean window.

So: the right answer in this phase comes from less context, not more.

## Scope boundary — what you can and can't read

You may read:

- `phases/1-research/artifacts/RESEARCH.md` (the locked Phase 1 artifact)
- The task prompt
- `skills/*/SKILL.md` metadata (frontmatter only — for routing)
- This README
- **References named by filename in RESEARCH.md's `## References cited`
  section.** Cited-by-name only — not browsed, not inferred. If a reference
  doesn't appear in that list, you may not load it. This forces deliberate
  Phase 1 citation while preserving a recovery path: a thin RESEARCH.md
  whose `## References cited` was sloppy is still recoverable, just at the
  cost of a Phase-1 re-do.

You may **not** read:

- References NOT in RESEARCH.md's cited list. The cohort findings the Plan
  needs should already be summarized in RESEARCH.md by `§N` citation; the
  cited-by-name list lets you re-load the reference body if a citation is
  thin.
- `code/v1_baseline.py` — V1 numbers are constants of record.
- Any `models/<*>/predict.py` files.
- `MODELS.md` / `TREE.json` / `EXPERIMENTS.md`.

You may **not** write code. The output is `PLAN.md`, a markdown file.

## The candidates rule — ≥2, default 2, up to 3 with rationale

Plan ships **two candidates by default**: one rung-0 refinement + one
structurally-different. This keeps Phase 3's wall clock tractable and forces
a clean A/B comparison.

You may ship **three** candidates if RESEARCH.md surfaces two genuinely
distinct structural candidates that would each weaken the other slot in the
default pair (e.g. dynamic-ST and regime-switched both attack distinct
residual characters). Document the rationale in a `## Why three candidates`
section at the bottom of PLAN.md citing the specific RESEARCH.md findings
that motivate it. Without that rationale, default to two — committee mode
is the failure pattern the rule prevents.

At minimum **the plan must include one rung-0 refinement and one
structurally-different candidate** (rung-1+ OR orthogonal).

- **Candidate A — rung-0 refinement.** Inherits from V1, touches a small
  number of levers. Reliable. The role is to provide a floor: if B fails,
  A is the fallback that beats nothing-changed.
- **Candidate B — structurally different.** Either an **orthogonal**
  candidate (residual learner head on V1, regime-switched composite, etc.)
  **OR** a **rung-1+ structural climb** (dynamic single-track with fitted
  `C_αf, C_αr, Iz`, nonlinear tyre, etc.). The role is to generate signal
  about whether a structural change pays on this dataset.

**Orthogonal is a peer of rung-1, not a fallback.** The historically-winning
pair on this dataset is `(rung-0 bias correction) + (orthogonal residual
learner)` (cohort §2 + §4). Rung-1 is also admissible — cohort §1 + §7
show every prior attempt failed for under-parameterization, so it's the
higher-risk path, not the higher-status one. Choose rung-1 over orthogonal
only if your RESEARCH.md identifies a transient-dynamics signature a
residual learner cannot capture, and document the rationale in PLAN.md's
`why this rung over the alternative` field.

Both A and B must appear in the `RESEARCH.md` candidate list. The Plan
phase does not invent new candidates — it selects.

## Cohort-evidenced candidate sketches

These are starting points, not a menu to copy verbatim. Each cites the
cohort finding that motivates it (see `references/m4-cohort-findings.md`
section — already cited by your Phase 1 RESEARCH.md):

- **Rung-0 per-platform additive bias correction** (§2). +3.7-4.6% CTE
  reliably, no structural cost. Strong Candidate A default.
- **Rung-0 orthogonal residual learner on V1** (§4). +1-5% CTE reliably
  across shapes. Strong Candidate A if you'd rather pair it with a more
  ambitious B.
- **Rung-1 dynamic single-track with fitted `C_αf`, `C_αr`, `Iz`** (§1, §7).
  The starter scaffold is `_shared/rung1_starter.py`. Strong Candidate B
  default — it's the move the cohort has never demonstrated, so generating
  evidence here is high-value.
- **Rung-2 nonlinear tyre** (§1). Higher cost, higher ceiling. Candidate B
  if A already covers the per-platform bias correction lever.
- **Orthogonal regime-switched** (§3 + §8). Candidate B if your RESEARCH.md
  flagged distinct straight/transient regimes in the V1 residual.

## Critique-as-router in the Plan phase

`skills/critique-residuals/` is a typed-grounded router — given a residual
characterization (which you have from `RESEARCH.md`), it suggests a route.
You may run it on V1's residual character to inform Candidate A. Do not
treat its output as the decision — treat it as one input.

## The PLAN.md template

Copy this skeleton into `artifacts/PLAN.md` and fill it in.

```markdown
# PLAN.md — Phase 2 output

**Locked after phase 2 completes.** Do not edit in Phase 3.

## Selected candidates — ≥2, default 2, up to 3 with rationale

### Candidate A — rung-0 refinement

- **name**: <model-dir-name>          (will land at phases/3-implement/models/<name>/)
- **rung**: 0
- **parent**: v1
- **formulation summary**: <one paragraph>
- **levers being touched**: <list>
- **cohort precedent**: §<N> from m4-cohort-findings.md
- **dev-CV pass criterion**: yaw Δ% vs V1 < <threshold>, signed-bias warnings clear
- **estimated wall clock**: <minutes>

### Candidate B — structurally different (rung 1+ OR orthogonal)

- **name**: <model-dir-name>          (will land at phases/3-implement/models/<name>/)
- **rung**: `1 | 2 | 3 | orthogonal`   ← orthogonal is a peer, not a fallback
- **parent**: v1 (or A if B builds on A)
- **formulation summary**: <one paragraph>
- **fit strategy** (if rung 1+): MUST fit C_αf, C_αr, Iz — see `_shared/rung1_starter.py`
- **starter to use**: `_shared/rung1_starter.py` | residual-learner template | other
- **why this rung over the alternative**: (mandatory — cite the cohort
  evidence that swayed your choice between orthogonal and rung-1+)
- **cohort precedent / warning**: §<N> — and warnings from §1+§7 if rung-1
- **dev-CV pass criterion**: <threshold>
- **estimated wall clock**: <minutes>

## Phase 3 instructions

1. Build both candidates as `phases/3-implement/models/<A>/predict.py` and
   `phases/3-implement/models/<B>/predict.py`.
2. Each needs a `notes.md` declaring rung, parent, and expected residual.
3. Run `skills/iterate` on each (pass model_dir or cd into phases/3-implement/).
   The gate determines which (if any) goes to `final-model/`.
4. If both lose to V1 on dev CV, ship V1 with REPORT.md documenting why.
5. If parallel-rung subagent fan-out is wanted, use this PLAN.md as the
   manifest source for `launch-rungs/launch.sh`.

## What was deliberately excluded from the plan

- <candidate from RESEARCH.md you considered but rejected>: <one-sentence reason>
- <another>: <reason>

## Locking gate

After this PLAN.md is filled in:

  bash lock.sh phases/2-plan/artifacts/PLAN.md

`pre-flight-final-model` verifies PLAN.md is non-writable before the bundle
can ship.
```

## Hygiene

- Keep context fill below 40%. You should be nowhere near that with only
  `RESEARCH.md` + this README loaded.
- The plan does **not** decide which to ship — that's a Phase 3 decision
  based on dev-CV scores from `iterate`.
- The plan does not invent candidates Phase 1 didn't surface. If you find
  yourself wanting to, the right move is to fail this phase and re-run
  Phase 1 — not to smuggle the new candidate in.

## Locking — exit ritual

```bash
bash ../../lock.sh phases/2-plan/artifacts/PLAN.md
bash ../3-implement/run.sh
```
