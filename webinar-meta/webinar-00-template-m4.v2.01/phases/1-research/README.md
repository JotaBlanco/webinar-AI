# Phase 1 — Research

You are in the **Research** phase. Output: `phases/1-research/artifacts/RESEARCH.md`.

## Goal

Diagnose what's left to attack in V1's residual and enumerate ≥5 candidate
model formulations with cost annotations. This phase produces words, not
code. The next phase (Plan) will down-select from your list.

## Scope boundary — non-negotiable

- **No code.** No `predict.py`, no `_shared/` edits.
- **No `models/` directories.** `phases/3-implement/models/` stays empty
  through phase 1 and phase 2.
- **No scoring of new candidates.** You may run `skills/score-model` and
  `skills/residual-structure` on V1 to characterize its residual. That's it.
- **Do not edit `MODELS.md`, `TREE.json`, or `EXPERIMENTS.md`.** Those are
  Implement-phase artifacts; touching them here is a phase leak.

The artifact for this phase is `RESEARCH.md`. Nothing else.

## What to read

Required (load on entry, in this order):

1. `../../AGENTS.md` — operating contract reminder (8-column input, denied
   columns, V1 baseline numbers). Do **not** treat the root AGENTS.md as
   your guide — this README is your guide. Root AGENTS.md is for the contract.
2. `../../references/m4-cohort-findings.md` — 8 evidence-backed patterns.
   This is the load-bearing reference for the research phase. Pay close
   attention to §1 (rung-1 under-parameterization), §2 (per-platform
   additive bias), §4 (residual learner head), §6 (route-grouped CV), §7
   (rung-1 tooling gap), §8 (lag-τ refit failure).
3. `../../references/dynamics-formulations.md` — the V0/V1/rung-1/rung-2/
   rung-3 structural ladder. The "Minimum viable rung-1 attempt" section is
   essential for the rung-1 candidate.
4. `../../code/v1_baseline.py` — V1's actual code. Skim to understand which
   levers V1 already touches.

Optional (load if your candidate list reaches a topic they cover):

- `../../references/anti-patterns.md` — what cohorts mis-tried.
- `../../references/approach-menu.md` — option-space map; helpful for the
  "is this orthogonal or just a rung-0 variant?" question.
- `../../references/two-kpi-tradeoff.md` — when a candidate trades yaw for
  CTE, reference this.
- `../../references/ceiling-moves.md` — for genuinely orthogonal moves.

Do **not** load `references/closing-the-loop.md` — that's about the
inner-loop discipline, which is a Phase 3 concern.

## V1 residual diagnosis — how to do it

Before listing candidates, characterize what's left in V1. Run:

```python
# From the template root, or with PYTHONPATH=.
from skills.score_model.score import score_model
from code.v1_baseline import predict as v1_predict
# Score V1 on dev — DO NOT pass final=True here.
result = score_model(v1_predict, split="dev")

from skills.residual_structure.diagnose import diagnose_residual
verdicts = diagnose_residual(v1_predict, split="dev")
```

Record per platform: yaw RMSE, signed yaw bias, CTE RMSE, signed CTE drift,
and the residual-structure verdict (`noise_floor` vs `structure_detected:<reason>`).
This goes into the first table of `RESEARCH.md`.

Tesla has no truth — skip it (V0 passthrough is the honest fallback).

## Cohort findings to factor in

From `references/m4-cohort-findings.md`:

- **§2 — Per-platform additive bias correction** is the cheapest reliable
  CTE move (+3.7-4.6%, zero structural cost). Any candidate list missing a
  bias-correction variant is incomplete.
- **§4 — Residual learner head on V1** delivers +1-5% CTE reliably across
  shapes. This is your default rung-0 orthogonal candidate.
- **§1 + §7 — Rung-1 dynamic single-track**: every prior cohort attempt
  used `carParams` values verbatim and failed because `C_αf`, `C_αr`, `Iz`
  must be **fit per platform**. `_shared/rung1_starter.py` is the scaffold
  that closes this gap. Any rung-1 candidate in your list MUST commit to
  fitting these three, or it's repeating the cohort failure.
- **§6 — Route-grouped CV.** Candidates that lever per-route signals
  (asymmetric biases, route-conditional terms) need a route-grouped CV
  precondition or they overfit. Flag this in your cost annotation.

Cite findings by section number — `RESEARCH.md` lives long enough that
section numbers are more durable than quoted excerpts.

## The RESEARCH.md template

Copy this skeleton into `artifacts/RESEARCH.md` and fill it in.

```markdown
# RESEARCH.md — Phase 1 output

**Locked after phase 1 completes.** Do not edit in later phases.

## V1 residual diagnosis (per platform)

| platform | yaw RMSE | yaw signed bias | CTE RMSE | CTE drift | residual character |
|---|---|---|---|---|---|
| FORD_F_150_LIGHTNING_MK1 | | | | | |
| FORD_MUSTANG_MACH_E_MK1 | | | | | |
| HYUNDAI_IONIQ_5 | | | | | |
| TESLA_MODEL_3 | n/a | n/a | n/a | n/a | no truth — V0 passthrough |

## Candidates considered (≥5, ≥3 structurally distinct from V1)

For each: name, rung tag, expected residual attacked, cost annotation,
expected dev-CV magnitude (your prior, not a prediction).

1. **<name>** — rung `0|1|2|3|orth`
   - Attacks: <which platform's residual + which character>
   - Cost: <references / starters / skills needed>
   - Expected dev-CV: <±N% yaw, ±N% CTE>
   - Cohort precedent: <§N from m4-cohort-findings.md>

2. ...
3. ...
4. ...
5. ...

## References cited

<!--
LIST references you cited above by filename. Phase 2 may only re-load
references that appear in this list. Cite deliberately — Phase 2's
recovery path lives here.
-->

- references/m4-cohort-findings.md
-

## Cohort evidence to factor in

- §<N>: <one-liner: what the finding says + which candidate it informs>

## What this phase did NOT decide

- Which candidates to implement (Phase 2 — Plan)
- Which to ship (Phase 3 — Implement)
- Any code (Phase 3 — Implement)
```

## Hygiene

- Aim for 200-400 words in `RESEARCH.md` total.
- Keep context fill below 40%. If you're heading past it, you're loading
  too many references — pull back to the required four.
- Don't speculate beyond what the cohort + your V1 diagnosis support. The
  Plan phase has the harder task — give it useful options, not exhaustive
  ones.

## Locking — exit ritual

When `RESEARCH.md` is complete:

```bash
bash ../../lock.sh phases/1-research/artifacts/RESEARCH.md
```

(Run from the template root, or adjust the relative path.) The lock
makes the file read-only. Then proceed:

```bash
bash phases/2-plan/run.sh
```
