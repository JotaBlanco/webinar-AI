---
title: webinar-00-template-m4.v2 — Module 4 substrate (RPI-first lifecycle)
summary: m4.v2 takes the same five closed-loop mechanisms, V1 baseline, skills toolkit, references, and cohort findings as m4.v1, and reorganizes the framing so the Research → Plan → Implement lifecycle IS the spine. The directory layout reflects phases (phases/1-research/, phases/2-plan/, phases/3-implement/), the root AGENTS.md is an index, and per-phase READMEs carry the load-bearing guidance. Tree-search planning and parallel-rung subagents happen inside the Implement phase, after PLAN.md is locked.
tags: [template, webinar, m4, RPI, lifecycle, tree-search, cross-validation, parallel-subagents, lateral-fidelity]
updated: 2026-06-02
---

# webinar-00-template-m4.v2

Module 4 substrate for the lateral-fidelity webinar. **The v2 increment
over v1 is the framing**: same content, reorganized around the RPI
lifecycle as the spine rather than as opt-in scaffolding.

The agent enters at [`AGENTS.md`](AGENTS.md) — a ~50-line index that points
at the phase READMEs. The load-bearing guidance lives in
[`phases/1-research/README.md`](phases/1-research/README.md),
[`phases/2-plan/README.md`](phases/2-plan/README.md), and
[`phases/3-implement/README.md`](phases/3-implement/README.md). Each phase
README is the agent's complete guide for that phase only.

## The v2 thesis — why this contrasts with v1

m4.v1 makes RPI opt-in. Its AGENTS.md hands the agent the full operating
contract, the five mechanisms, the inner-loop recipe, the cohort findings,
and the test-split discipline all at once — and offers RPI / launch-rungs
as scaffolding the agent can choose to invoke. The agent has full
information available throughout.

m4.v2 makes RPI the **spine**: every action belongs to a phase, every
phase reads only what the prior phase produced. Context discipline is
enforced by the layout, not by the agent's restraint. The Plan phase has
no access to `references/` — the cohort findings it needs are already
cited by section number in the locked `RESEARCH.md`. The Implement phase
has no access to `RESEARCH.md`'s deliberation — it has only the two
candidates `PLAN.md` selected.

The bet: at 200k models with a ~40% smart-zone cliff (Horthy / HumanLayer
telemetry), the load-out of having all information available costs more
than it gains. v2 trades v1's flexibility for v1's discipline.

## Design principles

Inherited unchanged from v1:

1. **The verifier exists — use it.** `score-model` is a deterministic
   scorer against truth on dev. The 2026 verification-gap finding (CMU)
   doesn't apply here. Close the loop.
2. **Tree-search beats linear iteration on this task class.** AIDE
   (arxiv.org/abs/2502.13138) wins 4× more MLE-bench medals than the best
   linear agent. In v2 the search tree is planted in Plan (the two-candidates
   rule produces two children of V1) and grown in Implement.
3. **Verifier-guided agents lifted SWE-bench Verified +10.7 pts** with PRM
   course-correction. `skills/iterate` is the analogous mechanism.
4. **Cross-validation respects route grouping.** Agent-07's m3.v3 finding
   is the empirical motivation (the cohort paid for this lesson).
5. **Context discipline at the 40% inflection.** v2 hardens this from v1's
   opt-in RPI into the template's organizing principle.
6. **Structured divergence beats in-line "think harder."** Parallel rung
   subagents (in Phase 3) are context isolation, not personas. Anthropic
   Research / MAESTRO / arXiv 2509.22480.
7. **No persona multi-agent.** Same rationale as m3.v2 / v1.
8. **References + skills ratchet.** Cohort-evidenced findings replace
   themselves each cohort.

## File-by-file — the v2 layout

```
m4.v2/
├── AGENTS.md            (~50 lines — index only; points at phase READMEs)
├── README.md            (this file — human-facing v2 thesis)
├── MODELS.md            ← registry; auto-filled by skills/iterate (stays at root)
├── TREE.json            ← tree; auto-filled by skills/iterate (stays at root)
├── EXPERIMENTS.md       ← log; auto-filled by skills/iterate (stays at root)
├── phases/
│   ├── 1-research/
│   │   ├── README.md    (rich phase guide — required reading on phase entry)
│   │   ├── run.sh       (phase driver: seeds skeleton, prints next steps)
│   │   ├── PROMPT.md    (seed prompt to paste into a fresh session)
│   │   └── artifacts/   (RESEARCH.md lands here, then chmod -w)
│   ├── 2-plan/
│   │   ├── README.md
│   │   ├── run.sh
│   │   ├── PROMPT.md
│   │   └── artifacts/   (PLAN.md lands here, then chmod -w)
│   └── 3-implement/
│       ├── README.md    (the inner-loop recipe lives here, not at root)
│       ├── run.sh
│       ├── PROMPT.md
│       ├── artifacts/
│       └── models/      ← candidate model bundles live HERE in v2 (not at root)
├── lock.sh              ← shared chmod helper used by all three phases
├── launch-rungs/        ← invoked INSIDE phase 3, after PLAN.md is locked
├── skills/              ← unchanged from v1 (everything inherited + the m4 new ones)
├── references/          ← unchanged from v1
├── _shared/             ← unchanged (rung1_starter.py + cte math)
├── code/                ← unchanged (symlink stub)
├── data/                ← unchanged (symlink stub)
├── final-model/         ← only created by Implement phase
└── pyproject.toml       ← unchanged
```

What's different vs v1, concretely:

- The root `AGENTS.md` shrunk from ~190 lines to ~50.
- The old top-level `rpi/` directory is gone. Its contents moved into
  `phases/N-*/` with updated paths.
- Candidate models live under `phases/3-implement/models/<name>/`, not at
  template root. Registries (`MODELS.md`, `TREE.json`, `EXPERIMENTS.md`)
  stay at root so they survive phase compactions.
- `lock.sh` moved to the template root (was `rpi/lock.sh`).
- Each phase has its own `README.md` (rich, ~150-250 lines) and `PROMPT.md`
  (short seed prompt, ~30 lines).

## What we deliberately did *not* add

Identical to v1:

- **Persona / multi-role subagents.** `launch-rungs/` is context isolation,
  not role-play.
- **Model self-judging best-of-N without the real scorer.** The verification
  gap *widens* with N.
- **External SaaS sandboxes (Modal, E2B).** Task runs locally on CPU.
- **LLM-as-judge as a quality gate.** `critique-residuals` is a
  typed-grounded router.
- **Cohort-level automated skill ratchet.** Held for a later module — see § "What m5 owes m4" below.

## What m5 owes m4 — the unclosed loop

m4 closes the inner loop (every iteration auto-scores, auto-logs, auto-routes)
but does not close the **cross-cohort loop**: `references/m4-cohort-findings.md`
was curated from the m3.v3 cohort by hand. m5's responsibility is to ship a
skill — provisionally `crystallise-cohort-findings` — that ingests the m4
cohort's REPORT.md files + assessment.md verdicts + TREE.json data, finds
the patterns that recur across runs, and emits the next iteration's
cohort-findings reference automatically.

Without this skill, the m4 ratchet stops after one cohort. The next cohort
inherits stale findings, the references drift out of sync with reality, and
the cohort-evidenced routing in `critique-residuals` decays. The placeholder
exists here so the gap is named, not silently inherited.

## How to drive Module 4 v2 with this template

1. Symlink `data/` and `code/` into the agent's working dir
   (see [data/README.md](data/README.md), [code/README.md](code/README.md)).
   The code symlink must contain `v1_baseline.py` (m3.v3+).
2. Open the agent dir in Claude Code. `AGENTS.md` loads — but it just
   points at the phase READMEs.
3. The agent's task prompt names the two KPIs + V1's pooled scores as floor.
4. **Phase 1.** `bash phases/1-research/run.sh`. Fresh session uses
   `phases/1-research/PROMPT.md` to bootstrap. Produces `RESEARCH.md`,
   locked.
5. **Phase 2.** `bash phases/2-plan/run.sh`. Fresh session uses
   `phases/2-plan/PROMPT.md`. Reads only `RESEARCH.md`. Produces `PLAN.md`,
   locked.
6. **Phase 3.** `bash phases/3-implement/run.sh`. Fresh session uses
   `phases/3-implement/PROMPT.md`. Reads only `PLAN.md` + skills. Builds,
   runs the iterate loop, ships `final-model/`. Optionally invokes
   `launch-rungs/launch.sh` here.
7. End gate: `pre-flight-final-model --final` reads the frozen test split,
   reports dev/test gap, ships if within band. Locks on `RESEARCH.md` and
   `PLAN.md` are verified by the preflight.

## Dependencies

- Python 3.11+
- `uv` (`uv sync` after first clone)
- `yq` for launch-rungs manifest parser (`brew install yq`)
- Claude Code
- (optional) matplotlib for PNG tree visualisation

## Sources informing m4 (same as v1)

Internal:
- m3.v3 cohort grade — `_grade/20260601-173918/cohort.md`
- m3.v3 cohort reports — `module-3.v3/agent-{01..10}/REPORT.md`
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
  organizing principle, where it informed v1 as one mechanism among five.
- HumanLayer 100K-session telemetry (40% context-fill inflection)
