---
title: webinar-00-template-m4.v1.01 — Module 4 substrate (m4.v1 + cohort-evidenced gates)
summary: m4.v1.01 patches m4.v1 in response to the m4.v1 cohort grading. The median m4.v1 agent (+56.2% yaw / +71.1% CTE) matched m3.v2 (+56.6% / +72.2%), but two stragglers — agent-07 (per-platform bias on an i.i.d. holdout) and agent-10 (built on V0 instead of V1) — shipped fast and dragged the mean. m4.v1.01 closes those modes with hard gates (bias_without_route_cv, parent_baseline_declared, iterate_history_min, report_cites_rejected), bumps budgets (orchestrator 45→90 min, subagents 25-30→45-60 min) to remove the time-pressure rationalisation, expands the launch-rungs fan-out from 4 to 6 subagents (adds rung-0-orth-gb and rung-2-lightning-targeted — Lightning is the headroom platform at +21% vs +55% for the others), and reframes budgets as floors rather than ceilings. All five m4.v1 closed-loop mechanisms (iterate, route-grouped CV, RPI, launch-rungs, typed-grounded router) are inherited unchanged; only the gates around them tightened.
tags: [template, webinar, m4, m4.v1.01, tree-search, RPI, cross-validation, parallel-subagents, lateral-fidelity, cohort-evidenced-gates]
updated: 2026-06-02
parent_template: webinar-00-template-m4.v1
---

# webinar-00-template-m4.v1.01

Module 4 substrate for the lateral-fidelity webinar — **m4.v1 with the
gates the m4.v1 cohort proved necessary.** The closed-loop mechanisms,
skills toolkit, references, and rpi/ phase scaffolding are all inherited
unchanged from m4.v1. What changed:

- **Hard gates** for the two observed m4.v1 failure modes
  (`bias_without_route_cv`, `parent_baseline_declared`,
  `iterate_history_min`, `report_cites_rejected`).
- **Generous budgets** (orchestrator 90 min, subagents 45–60 min) framed
  as floors not ceilings.
- **6-way launch-rungs fan-out** (was 4), with new rung-0-orth-gb and
  rung-2-lightning-targeted slots.
- **PLAN.md default of 3 candidates** (was 2) with Lightning as the
  default Candidate C target.
- **MODELS.md minimum bumped 4→6** with ≥2 structurally-different.
- **Cohort-§6 prior wired inline** into critique-residuals's router as
  the new `add_route_cv_for_bias` route.

See [`references/m4-cohort-findings.md`](references/m4-cohort-findings.md)
§9 for the cohort-evidence narrative.

The agent reads [`AGENTS.md`](AGENTS.md) — authoritative source for layout,
mechanisms, and inner-loop recipe. This README is for the human setting up
the template.

## Design principles

Informed by the m1+m2+m3.v2+m3.v3 cohort grades and recent (Jan-June 2026)
AI engineering writing:

1. **The verifier exists — use it.** `score-model` is a real deterministic
   scorer against truth on dev. Almost every 2026 test-time-scaling finding
   is bottlenecked by the "verification gap" (CMU 2026: model self-selection
   closes ~55% of oracle gap, gap *widens* with N). m4 doesn't have that
   bottleneck. Close the loop.
2. **Tree-search beats linear iteration on this task class.** AIDE
   (`arxiv.org/abs/2502.13138`) wins 4× more MLE-bench medals than the best
   linear agent. AlphaEvolve / CodeEvolve recipe applies.
3. **Verifier-guided agents lifted SWE-bench Verified +10.7 pts** with PRM
   course-correction (Sep 2025). The `iterate` skill is the analogous
   mechanism here — auto-firing computational sensors gate every model entry
   into the registry.
4. **Cross-validation respects route grouping.** Agent-07's m3.v3 finding
   (asymmetric-bias subset fit flipped Lightning sign) is the empirical
   motivation. The cohort already paid for this lesson.
5. **Context discipline at the 40% inflection.** RPI phase separation
   (Horthy, HumanLayer 100K-session telemetry) is hard-locked because soft
   discipline blurs under pressure.
6. **Structured divergence beats in-line "think harder."** Parallel rung
   subagents are context-isolation, not personas. Anthropic Research's
   90.2% internal-eval lift + MAESTRO + arXiv 2509.22480.
7. **No persona multi-agent.** Same rationale as m3.v2 (Cognition,
   Wasowski, Anthropic production patterns) — hardened in 2026.
8. **References + skills ratchet.** Same pattern m2/m3 use. The new
   `m4-cohort-findings.md` is the first cohort-evidenced reference in m4;
   the next cohort's findings replace it.

## What m4 adds — file-by-file

**New skills** (in [`skills/`](skills/)):

- [`iterate/`](skills/iterate/) — one-shot tree-search step. Model-shape-agnostic.
  Runs the verifier gate (CV + residual + diff vs parent vs V1 vs leader),
  appends to TREE.json + MODELS.md + EXPERIMENTS.md, returns routing dict.
- [`critique-residuals/`](skills/critique-residuals/) — typed-grounded router
  (not judge). Emits one of a fixed set of routes whose precondition is
  mechanically verifiable from the gate output.
- [`visualise-tree/`](skills/visualise-tree/) — render TREE.json as ASCII /
  markdown / PNG. Spot stagnation and rung collapse visually.
- [`score-model/cv.py`](skills/score-model/cv.py) — k=5 route-grouped CV
  wrapper around `score()`, with test-split refusal.
- [`assess-candidate-model/`](skills/assess-candidate-model/) — inherited
  unchanged from m3.v3.
- [`pre-flight-final-model/`](skills/pre-flight-final-model/) — adds 5
  m4-specific gates (MODELS.md candidate floor, TREE.json consistency,
  rung diversity, RPI lock, test-split gate).

**New code** (in [`_shared/`](_shared/)):

- [`rung1_starter.py`](_shared/rung1_starter.py) — linear dynamic single-track
  scaffold with RK4 integration and `fit_calpha_and_iz()`. Closes the m3.v3
  cohort tooling gap (§7) that blocked every rung-1 attempt.

**New scaffolding** (root):

- [`launch-rungs/`](launch-rungs/) — parallel divergent subagent manifest +
  launch script. 4 subagents by default.
- [`rpi/`](rpi/) — three-phase RPI driver with hard-locked artifacts.
- [`MODELS.md`](MODELS.md) — registry schema. Now includes `parent:` field.
- [`TREE.json`](TREE.json) — machine-readable tree managed by `skills/iterate`.

**New references** (in [`references/`](references/)):

- [`m4-cohort-findings.md`](references/m4-cohort-findings.md) — 8
  evidence-backed patterns from the m3.v3 cohort. Cited by
  `critique-residuals` via section number.
- [`closing-the-loop.md`](references/closing-the-loop.md) — how the five
  m4 mechanisms compose. Read first.

**m4.v1 is strictly additive over m3.v3.**

## What we deliberately did *not* add

- **Persona / multi-role subagents.** Same rationale as m3.v2 (Cognition,
  Wasowski, Anthropic production patterns 2026). `launch-rungs/` is context
  isolation, not role-play.
- **Model self-judging best-of-N without the real scorer.** The verification
  gap *widens* with N.
- **External SaaS sandboxes (Modal, E2B).** Task runs locally on CPU.
- **LLM-as-judge as a quality gate.** `critique-residuals` is typed-grounded
  router (only emits routes whose preconditions it can verify from gate
  output). Avoids the 2026 self-refine "coherence trap."
- **Cohort-level automated skill ratchet.** Held for a later module — see § "What m5 owes m4" below.

## What m5 owes m4 — the unclosed loop

m4 closes the inner loop (every iteration auto-scores, auto-logs, auto-routes)
but does not close the **cross-cohort loop**: `references/m4-cohort-findings.md`
was curated from the m3.v3 cohort by hand. m5's responsibility is to ship a
skill — provisionally `crystallise-cohort-findings` — that ingests the m4
cohort's REPORT.md files + assessment.md verdicts + TREE.json data, finds
the patterns that recur across runs (winning structures, failure modes,
specific cohort-level evidence), and emits the next iteration's
`m4-cohort-findings.md` (renamed `m5-cohort-findings.md`) automatically.

Without this skill, the m4 ratchet stops after one cohort. The next cohort
inherits stale findings, the references drift out of sync with reality, and
the cohort-evidenced routing in `critique-residuals` decays. The placeholder
exists here so the gap is named, not silently inherited.

## How to drive Module 4 with this template

1. Symlink `data/` and `code/` into the agent's working dir
   (see [data/README.md](data/README.md), [code/README.md](code/README.md)).
   The code symlink must contain `v1_baseline.py` (m3.v3+).
2. Open the agent dir in Claude Code. `AGENTS.md` loads.
3. The agent's task prompt names the two KPIs + V1's pooled scores as floor.
4. Inner loop: build `models/<name>/` → `skills/iterate` → follow the route.
5. Optional: `bash rpi/run-research.sh` for phase-separated research; or
   `bash launch-rungs/launch.sh` for parallel rung subagents.
6. End gate: `pre-flight-final-model --final` reads the frozen test split,
   reports dev/test gap, ships if within band.

## Dependencies

- Python 3.11+
- `uv` (`uv sync` after first clone)
- `yq` for launch-rungs manifest parser (`brew install yq`)
- Claude Code
- (optional) matplotlib for PNG tree visualisation

## Sources informing m4

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
- Horthy, Advanced Context Engineering (RPI loop)
- HumanLayer 100K-session telemetry (40% context-fill inflection)
