# RPI — Research → Plan → Implement (hard-locked artifacts)

## What it is

Three-phase workflow with **hard-locked** artifacts between phases. Each phase
runs in a fresh Claude Code session with its context window seeded by *only*
the prior phase's locked artifact (plus skills + references). This bounds
context-fill below the 40% inflection across all three phases — empirical:
HumanLayer 100K-session telemetry shows the smart-zone cliff at ~40% fill on
200k models.

Source: Dex Horthy, "Advanced Context Engineering" / RPI.

## Why this matters for m4

Cohort evidence (m3.v3): every agent that considered rung-1 made the decision
*during implementation*, when their context was already at ~60-70% fill from
hours of rung-0 work. By that point the cognitive cost of climbing a rung
looked higher than it actually was. RPI moves the rung-1 decision into the
Plan phase, where the context is fresh and the decision is cheap.

## The three phases

### Phase 1 — Research

Fresh session. Reads: AGENTS.md, references/, V1 baseline + V1 score, the
task prompt. Writes: `RESEARCH.md` listing candidate model formulations with
expected cost/benefit. **No code.** Locked at phase end (chmod -w).

```bash
bash rpi/run-research.sh
```

Output target: `rpi/artifacts/RESEARCH.md` — 200-400 words, structured as:
- "What's left to attack in V1's residual" (one paragraph per platform)
- "Candidates considered" (≥5, with rung tag + expected residual character)
- "Cost annotations" (which references / starters / skills each candidate needs)

### Phase 2 — Plan

Fresh session. Reads: ONLY `RESEARCH.md` + the task prompt + skill metadata.
Writes: `PLAN.md` naming exactly 2 candidates to implement — **one rung-0
refinement, one rung-1+ structural climb**. Plan is locked (chmod -w) before
phase 3.

```bash
bash rpi/run-plan.sh
```

Output target: `rpi/artifacts/PLAN.md` — names two candidate model directories,
specifies the rung tag, references the cohort-evidenced starter (`_shared/rung1_starter.py`
for rung-1+), and lists the gate-pass criteria. Plan does **not** decide which
to ship — that's an implementation-phase decision based on dev-CV scores.

### Phase 3 — Implement

Fresh session. Reads: ONLY locked `PLAN.md` + skills + references the plan
names. Writes: both `models/<name>/predict.py` candidates. Runs `iterate` on
each. Picks the dev-CV winner. Ships.

```bash
bash rpi/run-implement.sh
```

The locking mechanism (`rpi/lock.sh`) makes RESEARCH.md and PLAN.md read-only
once their phase ends. This is mechanical, not discipline — `pre-flight-final-model`
checks the artifacts are locked and rejects the bundle if they aren't.

## Files

- [`run-research.sh`](run-research.sh) — phase-1 driver
- [`run-plan.sh`](run-plan.sh) — phase-2 driver
- [`run-implement.sh`](run-implement.sh) — phase-3 driver
- [`lock.sh`](lock.sh) — chmod-ro helper called by each phase
- [`templates/RESEARCH.md.template`](templates/RESEARCH.md.template) — phase-1 output skeleton
- [`templates/PLAN.md.template`](templates/PLAN.md.template) — phase-2 output skeleton
- `artifacts/` — output dir (gitignored; one set per run)

## Relationship to parallel-rung subagents

RPI and parallel rungs are orthogonal:

- **RPI** controls the *phases* of work (research → plan → implement) within a
  single rung's pursuit.
- **Parallel rungs** controls the *structural diversity* across rungs.

The cleanest combination: run RPI's research + plan in one session, then in
phase 3 launch parallel-rung subagents to do the *implementing*, each in its
own fresh context. The Plan phase's `PLAN.md` becomes the parallel launch
manifest. Use whichever combo your budget supports — both work standalone.

## Soft fallback

If you cannot lock files in your environment, the RPI discipline can still
work via session boundaries alone — start each phase in a fresh terminal/IDE
window and feed only the prior artifact. The locking is the strict gate;
the session reset is the load-bearing part.
