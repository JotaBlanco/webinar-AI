---
title: webinar-00-template-m4.v2.01 — Module 4 substrate (RPI-first lifecycle + prefilled physics ladder)
summary: m4.v2.01 keeps the RPI-first lifecycle from m4.v2 and adds a prefilled physics-model ladder at phases/3-implement/models/. Five candidates (LDST, Fiala, double-track+LLT, relaxation-length, friction-circle) ship runnable end-to-end with fit/eval/validate scripts; a frozen route-grouped train/dev/test split eliminates split drift across agents; a new diagnose-by-physics-regime skill routes residuals to the right candidate; F150 yaw ceiling documented as a known constraint. Designed to break the 90-agent yaw ≈+57% / CTE ≈+72% plateau by removing the activation-energy cost of climbing past rung 0.
tags: [template, webinar, m4, RPI, lifecycle, tree-search, cross-validation, parallel-subagents, lateral-fidelity, prefilled-physics, dynamics-ladder]
updated: 2026-06-03
---

# webinar-00-template-m4.v2.01

Module 4 substrate for the lateral-fidelity webinar. **The v2.01 increment
over v2 is structural prefill, not framing**: the RPI-first lifecycle is
unchanged, but the Implement phase now ships with five fully-runnable
physics candidates, a frozen evaluation split, and a residual-routing
skill that maps "where the error lives" to "which candidate to run."

## The v2.01 thesis — why this re-cuts v2

m3.v2, m3.v3, m4.v1, and m4.v2 — **90 agents on the same idea** —
converged on the same plateau: yaw ≈+57% / CTE ≈+72% improvement vs V0.
Every winner shipped a refined rung-0 model (kinematic single-track +
understeer + first-order yaw lag + per-segment δ₀), often with a residual
ridge layer. **Zero agents shipped a rung-1 (dynamic) model in 90
attempts.** The dynamics ladder has never been climbed.

m4.v2's RPI lifecycle was bypassed by all 10 agents: 0 of them produced
`RESEARCH.md` / `PLAN.md` artifacts. They went straight to implementation,
plateau'd in V1's neighbourhood, and shipped — at +30 % token cost vs m4.v1
for the same scores. The phase folders added ceremony without changing
search behaviour.

The v2.01 hypothesis: agents don't climb the rung because the
**activation energy** is too high. Writing rung 1 from scratch under a
60-min budget against an opaque ODE-integration risk lost every time to
"just refine V1." If rung 1 (and 2, 3, orthogonal) is *already runnable*
on day one, the trade reverses.

## What's different from m4.v2

| change | rationale |
|---|---|
| **5 physics models prefilled** at `phases/3-implement/models/` | All rung ≥ 1. Runnable on day one. Each ships `model.py + fit.py + eval.py + validate.py + coeffs.json + notes.md + README.md`. Removes "I'd write rung 1 if I had time." |
| **Frozen route-grouped train/dev/test split** at [`_shared/frozen_split.py`](_shared/frozen_split.py) | Eliminates "I can't trust my metrics without reading prior cohorts" — agent-10's m4.v2 complaint, verbatim. Same partition every agent, every run. |
| **`_shared/physics_core.py`** | RK4, slip angles, axle loads, Fiala tire, lateral load transfer, friction circle, relaxation length as one library. Bug fixed once = fixed everywhere. |
| **`diagnose-by-physics-regime` skill** | Slices residuals into five physics regimes (transient steering / high-`a_lat` / heavy load transfer / brake-or-accel / speed-dependent phase lag) that map 1:1 to M1–M5. Replaces "stare at score-model output and guess." |
| **F150 ceiling doc** at [`references/f150-yaw-ceiling.md`](references/f150-yaw-ceiling.md) | Documents the +21 % yaw floor F150 has shown across 90 agents. Points at M3 (double-track + load transfer) as the right hypothesis. Stops rung-0 retuning tangents. |
| **`references/dynamics-formulations.md`** — M2/M3/M4/M5 sections fleshed out | Were sketches in m4.v2; now full equations, parameter tables, when-this-helps / failure-mode pairs. |
| **TASK.md — 90-min soft budget** with a phased spend | Was an implicit 60 min before. The phased spend (15 / 20 / 40 / 15) gives breathing room for fit + iterate without blowing past validation. |
| **MODELS.md / TREE.json prepopulated** with V1 + 5 child nodes | Tree-search frontier visible from minute one. Status `drafting` until agent fits and `iterate`s a candidate. |
| **`make-train-dev-split` deterministic across processes** | Patched the pre-existing `hash(platform)` bug with `zlib.crc32(...)`. Same seed now genuinely reproduces. |

## The 5 prefilled candidates

| dir | model | rung | targets |
|---|---|---|---|
| [`phases/3-implement/models/m1-linear-dynamic-st/`](phases/3-implement/models/m1-linear-dynamic-st/)                       | Linear dynamic single-track            | 1          | transient regime, phase lag |
| [`phases/3-implement/models/m2-fiala-tire-st/`](phases/3-implement/models/m2-fiala-tire-st/)                               | Fiala nonlinear tire on M1             | 2          | high-`a_lat` saturation |
| [`phases/3-implement/models/m3-double-track-load-transfer/`](phases/3-implement/models/m3-double-track-load-transfer/)     | Double-track + lateral load transfer   | 3          | F150 yaw ceiling |
| [`phases/3-implement/models/m4-relaxation-length/`](phases/3-implement/models/m4-relaxation-length/)                       | Distance-domain tire relaxation        | orthogonal | speed-dependent phase lag |
| [`phases/3-implement/models/m5-friction-circle/`](phases/3-implement/models/m5-friction-circle/)                           | Long-lat coupling via friction circle  | 3          | brake-in-corner, accel-out |

Full derivations in [`references/dynamics-formulations.md`](references/dynamics-formulations.md).

## Headline at default priors (dev split, n = 402)

| model | yaw RMSE | CTE RMSE | notes |
|---|---:|---:|---|
| V1 (m3.v3 leader, constants of record) | 0.005874 | 56.81  | floor |
| M1 LDST (unfit priors)                 | 0.00919  | 116.89 | needs fit |
| M2 Fiala (unfit priors)                | 0.00921  | 116.89 | needs fit |
| M3 DT+LLT (unfit priors)               | 0.00921  | 116.89 | needs fit |
| **M4 Relax-length (σ=0.5)**            | **0.00585** | 52.13 | already ~V1 at default σ |
| M5 Friction-circle (unfit priors)      | 0.00919  | 116.89 | needs fit |

M4 is the standout pre-fit signal: at the default `σ=0.5 m` it already
ties V1 on yaw and edges it on CTE (52 m vs 57 m). **The orthogonal
model pays off without any fitting** — supports the cohort thesis that
distance-domain phase lag is the right formulation. The dynamics ladder
models (M1/M2/M3/M5) need their fits to clear the V1 bar; that's the
90-minute agent job.

The pre-fit dynamics models cluster (0.00919–0.00921) because in the
small-angle regime their physics differ negligibly; they only diverge
materially under fitting and at the high-`a_lat` / load-transfer
extremes the dataset is sparse in. The `diagnose-by-physics-regime`
skill surfaces where each one's signal will live.

## The v2 framing — kept unchanged

You are operating an **RPI-first** template. Research → Plan → Implement
is the spine: every action belongs to a phase, every phase reads only
what the prior phase produced. Start at
[`phases/1-research/README.md`](phases/1-research/README.md). The root
[`AGENTS.md`](AGENTS.md) is an index; the load-bearing guidance lives
in the per-phase READMEs.

The bet (unchanged from m4.v2): at 200k models with a ~40 % smart-zone
cliff (Horthy / HumanLayer telemetry), the load-out of having all
information available costs more than it gains. v2.01 keeps v2's trade
(flexibility for discipline) and adds prefill so the discipline doesn't
also cost the activation energy of building rung 1 from scratch.

## Design principles

Inherited unchanged from v1/v2:

1. **The verifier exists — use it.** `score-model` is a deterministic
   scorer against truth on dev. The 2026 verification-gap finding (CMU)
   doesn't apply here. Close the loop.
2. **Tree-search beats linear iteration on this task class.** AIDE
   (arxiv.org/abs/2502.13138) wins 4× more MLE-bench medals than the best
   linear agent. In v2.01 the tree is *planted* with five physics
   children of V1 from minute one and grown by `iterate` during Implement.
3. **Verifier-guided agents lifted SWE-bench Verified +10.7 pts** with PRM
   course-correction. `skills/iterate` is the analogous mechanism.
4. **Cross-validation respects route grouping.** Agent-07's m3.v3 finding.
   v2.01 hardens this into the frozen split.
5. **Context discipline at the 40 % inflection.** v2's organising principle.
6. **Structured divergence beats in-line "think harder."** Parallel rung
   subagents (in Phase 3) are context isolation, not personas.
7. **No persona multi-agent.** Same rationale as m3.v2 / v1.
8. **References + skills ratchet.** Cohort-evidenced findings replace
   themselves each cohort.

## File-by-file layout

```
webinar-00-template-m4.v2.01/
├── AGENTS.md                  (~50 lines — index only; points at phase READMEs)
├── README.md                  (this file — human-facing v2.01 thesis)
├── TASK.md                    (the task framing + 90-min budget)
├── MODELS.md                  ← prepopulated registry (V1 root + 5 children)
├── TREE.json                  ← prepopulated tree (same)
├── EXPERIMENTS.md             ← log; auto-filled by skills/iterate
├── phases/
│   ├── 1-research/            (rich phase guide + run.sh + PROMPT.md + artifacts/)
│   ├── 2-plan/                (same shape)
│   └── 3-implement/
│       ├── README.md
│       ├── run.sh, PROMPT.md, artifacts/
│       └── models/            ← **prefilled with M1–M5**
├── lock.sh                    ← shared chmod helper used by all three phases
├── launch-rungs/              ← invoked INSIDE phase 3, after PLAN.md is locked
├── skills/                    ← v2 skill set + new `diagnose-by-physics-regime`
├── references/                ← v2 references + `f150-yaw-ceiling.md` + `held-out-split.md`
│                                + fleshed-out `dynamics-formulations.md`
├── _shared/
│   ├── traj_metrics.py        (cte / yaw math, shared with grade-cohort-reports)
│   ├── rung1_starter.py       (kept for backward compatibility)
│   ├── physics_core.py        ← **new** — RK4 / slip / Fiala / load-transfer / friction-circle / relaxation
│   └── frozen_split.py        ← **new** — deterministic 60/20/20 route-grouped split
├── code/                      ← symlink stub (filled at fan-out)
├── data/                      ← symlink stub (filled at fan-out)
├── final-model/               ← only created by Implement phase
└── pyproject.toml
```

What's different vs v2, concretely:

- `phases/3-implement/models/` is **prefilled with five candidates** (was empty in v2).
- `_shared/` gains `physics_core.py` (~250 lines) and `frozen_split.py` (~100 lines).
- `skills/` gains `diagnose-by-physics-regime/` and a patched `make-train-dev-split/split.py` (CRC32, not `hash()`).
- `references/` gains `f150-yaw-ceiling.md` and `held-out-split.md`; `dynamics-formulations.md` grows ~3× (M2/M3/M4/M5 are full sections, not sketches).
- `MODELS.md` and `TREE.json` are prepopulated, not empty.
- `TASK.md` documents the 90-min phased budget.

## How to drive Module 4 v2.01 with this template

1. Symlink `data/` and `code/` into the agent's working dir
   (see [data/README.md](data/README.md), [code/README.md](code/README.md)).
   The code symlink must contain `v1_baseline.py` (m3.v3+).
2. Open the agent dir in Claude Code. `AGENTS.md` loads — but it just
   points at the phase READMEs.
3. The agent's task prompt names the two KPIs + V1's pooled scores as floor.
4. **Phase 1.** `bash phases/1-research/run.sh`. Fresh session uses
   `phases/1-research/PROMPT.md` to bootstrap. Produces `RESEARCH.md`,
   locked. **Suggested first move:** run
   `python skills/diagnose-by-physics-regime/diagnose.py` against V1 to
   see which of the five prefilled candidates the residual points at.
5. **Phase 2.** `bash phases/2-plan/run.sh`. Fresh session uses
   `phases/2-plan/PROMPT.md`. Reads only `RESEARCH.md`. Produces `PLAN.md`,
   locked.
6. **Phase 3.** `bash phases/3-implement/run.sh`. Fresh session reads
   `PLAN.md` + skills + the prefilled `models/` tree. Runs `fit.py && eval.py`
   on the top candidates from the routing, iterates via `skills/iterate`,
   ships `final-model/`.
7. End gate: `pre-flight-final-model --final` reads the frozen test split
   via `_shared/frozen_split.test_paths()`, reports train→dev→test
   progression, ships if within band. Locks on `RESEARCH.md` and
   `PLAN.md` are verified by preflight.

## What we deliberately did *not* add

Identical to v2:

- Persona / multi-role subagents. `launch-rungs/` is context isolation,
  not role-play.
- Model self-judging best-of-N without the real scorer. The verification
  gap *widens* with N.
- External SaaS sandboxes (Modal, E2B). Task runs locally on CPU.
- LLM-as-judge as a quality gate. `critique-residuals` is a
  typed-grounded router.

New for v2.01 — deliberately NOT done:

- **Pacejka magic-formula tire** as a sixth prefilled model. 8 params per
  axle ≈ 24 fitted parameters per platform with insufficient saturation
  in the dataset. Fiala (M2) gets the saturation signal at 3 params per
  axle. Pacejka can be added by an agent if their residual demands it.
- **Suspension / body-roll states.** The data doesn't include suspension
  height or roll-rate channels; modelling them is unidentifiable.
- **Multi-body Rung 3** (full vehicle CAD-grade). Overkill for 2901-row
  segments and the test pool's distribution.

## What m5 owes m4 — the unclosed loop (unchanged from v2)

m4 closes the inner loop (every iteration auto-scores, auto-logs,
auto-routes) but does not close the **cross-cohort loop**:
`references/m4-cohort-findings.md` was curated from the m3.v3 cohort by
hand. m5's responsibility is to ship a skill — provisionally
`crystallise-cohort-findings` — that ingests the m4 cohort's REPORT.md
files + assessment.md verdicts + TREE.json data, finds the patterns that
recur across runs, and emits the next iteration's cohort-findings
reference automatically.

Without this skill, the m4 ratchet stops after one cohort. v2.01 narrows
the gap by prefilling the *physics* — but the cohort-evidenced routing
in `critique-residuals` still decays without a crystallisation step.

## Dependencies

- Python 3.11+
- `uv` (`uv sync` after first clone)
- `yq` for launch-rungs manifest parser (`brew install yq`)
- Claude Code
- (optional) matplotlib for PNG tree visualisation

## Sources informing m4.v2.01

Internal:
- m3.v3 cohort grade — `_grade/20260601-173918/cohort.md`
- m3.v3 cohort reports — `module-3.v3/agent-{01..10}/REPORT.md`
- m4.v1 cohort grade — `_grade/20260602-215951/cohort.md`
- m4.v2 cohort grade — `_grade/20260602-223415/cohort.md` (the immediate motivation)
- AI-axis NC framework — `F1/KB002/ai-axis/_README.md`

External:
- AIDE — `arxiv.org/abs/2502.13138`
- AlphaEvolve — `arxiv.org/abs/2506.13131`
- CodeEvolve — `arxiv.org/abs/2510.14150`
- MLE-bench — `arxiv.org/abs/2410.07095`
- MAESTRO divergent-convergent — `arxiv.org/abs/2511.06134`
- Multi-Agent Verification — `arxiv.org/abs/2502.20379`
- CMU agent test-time-scaling ceiling (2026)
- Anthropic Multi-Agent Research (April 2025)
- Horthy, Advanced Context Engineering (RPI loop) — load-bearing for v2's
  organizing principle.
- HumanLayer 100K-session telemetry (40 % context-fill inflection).
- Pacejka, *Tyre and Vehicle Dynamics* — equations behind M2's Fiala
  approximation and M3's load-transfer formulation.
- Mitschke, *Dynamik der Kraftfahrzeuge* — relaxation-length (M4)
  derivation.
