# RPI loop instructions — Research → Plan → Implement

This task is large enough that running it as a single agent session degrades fast (Horthy's empirical curve: ~40% context fill = measurable failure rate). Run it as **three fresh agent sessions, three locked artifacts**.

You will produce three markdown files in `tasks/`:

```
tasks/
  challenge.md            ← the task statement (already exists, do not modify)
  research.md             ← phase 1 output, you will write it
  plan.md                 ← phase 2 output, you will write it (then LOCK before phase 3)
  implement-notes.md      ← phase 3 output, you will write it as you go
REPORT.md                 ← final deliverable at the workspace root
```

## Phase 1 — Research

**Fresh context window. Read this section + `tasks/challenge.md` + load the two skills metadata.**

Goal: understand the problem, the substrate, and the data — enough to plan honestly. Do **not** write code yet. Do **not** decide what fixes to ship — that's phase 2.

Produce `tasks/research.md` with:
1. **Substrate map.** What's in `code/`, what's in `data/`, what the operating contract is. Quote the key constraints (speed-known lateral-only; clamps; CSV schema). 1-2 short paragraphs.
2. **Baseline measurement.** Run `python code/generate_simdata_ford.py` if needed (sim CSVs may already exist — check first). Read at least one Ford sim.csv with code (not by eye). Report: RMSE ψ̇ in °/s per platform, RMSE a_y in m/s² per platform, correlation predicted-vs-measured, and qualitative shape of the residual (regime-dependence on v, |δ|, |a_y|). Cite the file paths and sample counts you used.
3. **Hypothesis space.** List 4-6 candidate improvements to the lateral fidelity. For each: physical mechanism, signature in the residual that supports it, ballpark expected effect size, implementation cost. No code yet — text only.
4. **Open questions.** What does the data not tell you? What references would you load (skill body, code file) in phase 2 to decide?

Target length: ~200 lines. Reading this in phase 2 should give a fresh window everything it needs without re-doing the exploration.

**Then exit the session.** The plan phase runs in a fresh window.

## Phase 2 — Plan

**Fresh context window. Read this section + `tasks/challenge.md` + `tasks/research.md` + the two skill bodies + only the code files you decide are needed.**

Goal: choose what to ship and write a step-by-step plan that phase 3 can execute without rediscovery.

Produce `tasks/plan.md` with:
1. **Selected improvements.** Pick 1-2 from the hypothesis space in `research.md`. State the *rationale* for each pick (expected impact / cost / risk).
2. **Implementation steps.** Numbered list. Each step: what file you'll touch, what change you'll make, how you'll verify it. Be concrete enough that phase 3 doesn't need to think creatively.
3. **Ablation design.** What runs you'll execute, in what order, to attribute residual delta to each change. Include the exact commands.
4. **Success criteria.** Quantitative: e.g., "RMSE ψ̇ reduced by ≥X% on Mach-E without regression on F-150" and "REPORT.md exists with the ablation table".

Target length: ~100 lines. **Lock this plan** — i.e., do not modify it in phase 3.

**Then exit the session.** The implementation phase runs in a fresh window.

## Phase 3 — Implement

**Fresh context window. Read this section + `tasks/plan.md` + `tasks/challenge.md` + the relevant skill bodies + the code files the plan names. Do NOT re-read `tasks/research.md`** — it's served its purpose.

Execute the plan as written. Write `tasks/implement-notes.md` as you go (notable surprises, deviations from the plan and *why*).

At the end, write `REPORT.md` at the workspace root per the deliverable spec in `tasks/challenge.md`.

If you discover phase 2's plan was wrong, do NOT silently improvise — record the issue in `implement-notes.md` and write the report against what you actually did, honestly.

## How to "run three sessions" inside one Claude invocation

You are a single Claude session, but you can *simulate* the three-phase discipline:

- **Phase 1**: Read only what phase 1 asks you to read. Write only `tasks/research.md`. When done, mentally close the window and clear your active focus.
- **Phase 2**: Read only what phase 2 asks you to read (in particular: do NOT keep recalling phase-1 exploration — work from `tasks/research.md` as if you'd never done phase 1). Write only `tasks/plan.md`.
- **Phase 3**: Read only what phase 3 asks for. Treat the plan as immutable. Write code, run ablation, write `tasks/implement-notes.md` and `REPORT.md`.

The artifacts are the connective tissue. The discipline is to write to them like you're handing off to a different engineer at each phase boundary — because in a real RPI loop, you are.
