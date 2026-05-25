# RPI loop — Research, Plan, Implement

> Non-trivial tasks in this workspace are run as **Research → Plan → Implement** across three fresh context windows, with markdown artifacts as the connective tissue. The plan is locked before implementation starts. This is the Planning component (4) of the harness.

## Why

A single long agent session forgets what it was doing past ~40% context fill (the "warm/dumb" curve). Splitting into three phases with markdown handoffs keeps each phase in the smart zone and creates an auditable trail.

## The artifacts

Three files per run, written into `rpi/runs/<timestamp>/`:

1. **`research.md`** — populated in phase 1 using [`templates/research.md`](templates/research.md).
2. **`plan.md`** — populated in phase 2 using [`templates/plan.md`](templates/plan.md), reading research.md only.
3. **`implement-notes.md`** — populated in phase 3 alongside any code/CSVs/plots, reading plan.md only.

## The discipline

- **Phase 1 — Research.** Read the challenge, the data, and AGENTS.md. Catalogue: what residuals look like, where they are worst, what failure modes the model exhibits. Output `research.md`. **Do not propose fixes here.**
- **Phase 2 — Plan.** Read only `research.md` (and templates/plan.md). Decide: which 1-2 improvements to implement, why, what success criterion, what ablation table to fill. Lock the plan. **Do not write code here.**
- **Phase 3 — Implement.** Read only `plan.md`. Execute. Fill the ablation table. Write `implement-notes.md` with what happened (what worked, what didn't, surprises).

If you compress the three phases into one, you lose the value. The point is to spend senior thinking on framing (phase 1) and design (phase 2) so the implementation is mechanical.

## How to use this in a single Claude Code session

If you cannot literally spin up three context windows, simulate the discipline:
- Stop and write `research.md` *first*, end-to-end, before opening any code editor.
- Stop and write `plan.md` *next*, end-to-end, before writing any python.
- Then implement.

The artifacts are the deliverable shape. The conversation is not.
