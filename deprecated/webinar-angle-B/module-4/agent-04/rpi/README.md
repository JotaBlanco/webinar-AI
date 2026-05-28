# rpi/ — Research → Plan → Implement scaffolding

This module uses the **RPI** discipline. The work is broken across three explicit phases. Each phase produces an artifact under `rpi/runs/<timestamp>/`. You do not move to the next phase until the current artifact is written. The artifacts are part of the deliverable.

## Phase 1 — Research (`research.md`)

Inspect the data, the model, the relevant skills. Surface the operating contract, the truth-channel-vs-prediction split, the baseline numbers, the plausible failure modes. Do **not** propose fixes yet. The point of the Research phase is to constitute the problem before solving it.

Use [`templates/research.md`](templates/research.md). Save as `rpi/runs/<timestamp>/research.md`.

## Phase 2 — Plan (`plan.md`)

State the variant ladder you intend to run. For each variant: the physical hypothesis, the one degree of freedom it adds, the predicted direction of its effect, and a falsifiable success criterion (e.g. "if `corr(resid, |a_y|)` does not drop, this variant did not address what I claimed"). **Lock the plan.** Once written, you do not change it during implementation — if a result invalidates the plan, you ship the partial and note the deviation. The lock is what makes attribution honest.

Use [`templates/plan.md`](templates/plan.md). Save as `rpi/runs/<timestamp>/plan.md`.

## Phase 3 — Implement (`implement-notes.md`)

Run the ladder in the order the plan locked. Write code under `tools/`, intermediate outputs under `out/`, the implementation diary under `rpi/runs/<timestamp>/implement-notes.md`. Note any deviation from the plan and why.

Use [`templates/implement-notes.md`](templates/implement-notes.md). Save as `rpi/runs/<timestamp>/implement-notes.md`.

## Then write the report

Only after the three artifacts exist do you write `REPORT.md`. The report references the three artifacts by path. The discipline is: **the plan is what you committed to, the implement-notes are what actually happened, and the report is the synthesis a stakeholder reads.** All three are public deliverables.

## Why this discipline

A free-form agent on a short task tends to discover something interesting, follow it, and silently drop the original framing. The RPI discipline is the lock that makes attribution honest: if you started with a hypothesis and the data killed it, *that* is the result, and the report says so. A senior engineer would not accept a result whose framing changed mid-investigation; this scaffolding is how you avoid that mid-investigation drift.
