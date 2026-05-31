---
title: webinar-00-template-m3 — Module 3 substrate (skills + references)
summary: Module-3 template for the lateral-fidelity webinar. Same eight-skill toolkit and shared math library as m2, plus six short domain-knowledge reference documents (anti-patterns + approach-menu + two-kpi-tradeoff with worked examples and failure-mode indexes; exploration-discipline; dynamics-formulations as a living catalogue agents extend; ceiling-moves) and an EXPERIMENTS.md log template. The references are the m3 increment over m2 — everything else is identical.
tags: [template, webinar, m3, skills, references, lateral-fidelity]
updated: 2026-05-31
---

# webinar-00-template-m3

Module 3 substrate for the lateral-fidelity webinar. **The m3 increment over m2 is the `references/` directory** — five short markdown files that name the levers, traps, and discipline prior cohorts needed. Skills, AGENTS.md framing, `_shared/` math, and the operating contract are identical to m2.

This README is for the human setting up the template. The agent reads [AGENTS.md](AGENTS.md) — that's the authoritative source for the working-directory layout, the skills inventory, the references inventory, and the modify-the-skill protocol. Don't duplicate that content here.

## Design principles

Informed by the m1+m2+m3 cohort grade at `_grade/20260531-003104/`, the KB002 NC catalogue, and recent (Dec 2025 – May 2026) context-engineering writing:

1. **Diagnostic surface, not polished oracle.** Inherited from m2: `scoring-model` returns per-segment tables, per-platform signed bias, distributions, dashboard. Not a single pooled number.
2. **Skills as clay, not library.** Inherited from m2.
3. **References carry the *why*, not just the rule** (Grove, NC-22). Each reference doc has worked examples drawn from prior top-performing agents — distribution and format matter more than principle correctness (Min et al.).
4. **References must be guides, not sensors** (NC-15 via BettaTech). Don't try to make a reference "detect" anything; that's an eval/judge job.
5. **References are ratcheted** (NC-14). Each new failure recurring across cohorts gets engineered into a reference as a new bullet, not re-prompted away.
6. **Failure-mode index pattern at the end of each reference** — recent practitioner consensus (Husain, Atlan harness-failures). Lead with success patterns; close with a failure checklist.
7. **Structured divergence beats in-line "think harder"** (arXiv 2509.22480). The exploration-discipline reference prescribes naming ≥3 genuinely different approaches before commitment, plus an `EXPERIMENTS.md` log to prevent silent re-convergence.

## What we deliberately did *not* add — and why

**Persona / "dream-team multi-role" subagents.** Tempting, but the 2026 literature has *hardened* against this:

- Horthy (*Advanced Context Engineering*): subagents are context-isolation primitives, not personas.
- Wasowski's *17 Multi-Agent Topologies* (May 2026): persona-stacking is the #1 budget-burn anti-pattern.
- Cognition's *Don't Build Multi-Agents* (June 2025) is still the reference position; subsequent vendor convergence (Anthropic, OpenAI, AutoGen, LangChain) is on **orchestrator + isolated subagents for context isolation only**, not role-play.
- Reported costs: multi-agent uses ~15× more tokens; strictly sequential tasks degrade 39–70% vs single agent.

Cohort-data check: in the m3 grading, mid-pack agents *correctly diagnosed* their residuals — they cited references by name and named the bias structure. They didn't fail for lack of perspective; they failed for lack of *concrete recipe knowledge*. A "yaw specialist" + "CTE specialist" split wouldn't have caught anything the references with worked examples already provide.

The narrow exception that survives in the literature — parallel divergent exploration with same-role subagents — is a *system-level* pattern (run N agents on the same task in parallel, merge the winner), not template content. If we want it later, it belongs in the launch skill, not in `references/`.

## What m3 adds — the references layer

Five short markdown documents under [`references/`](references/), each with a frontmatter `description` + `when-to-load`, a body that includes a worked example drawn from prior top-performing agents, and a failure-mode index at the end:

- **`anti-patterns.md`** — known traps. Distinguishes the *illegal* per-segment bias trick (uses truth at inference, submission fails) from the *legal* input-derived per-segment δ₀ (a winning move when platform-gated). Worked example: a ~40-line `predict()` from m3-agent-09's shipped model.
- **`approach-menu.md`** — option map. Annotated [explored] / [lightly tried] / [unexplored]. Includes platform-gating diagnostic. Worked example: polynomial g + per-segment δ₀ combo.
- **`two-kpi-tradeoff.md`** — KPI interpretation. Two-step diagnostic for "yaw improved but CTE stuck". Worked example: per-platform bias-spread check.
- **`exploration-discipline.md`** — protocol for naming ≥5 alternatives (at least 3 different model structures) before commitment + the `EXPERIMENTS.md` log convention.
- **`dynamics-formulations.md`** — V0 documented in full plus sketched rungs 1–3 (linear dynamic single-track with slip angles, nonlinear tyre, multi-body). **Living doc — explicitly designed to be appended-to by agents who ship a formulation past V0.** Includes a "Tried and shelved" section for dead ends so the next agent doesn't redo them.
- **`ceiling-moves.md`** — four moves above the current best-known ceiling (multi-seed fold averaging, CTE-aware fit, constrained joint fit, climb the structure ladder). With the `fit-model` skill now in the toolkit, several of these are one-line config changes rather than heavy lifts. Sequenced by residual shape. Only load after the agent has already beaten V0 by ≥+30% on both KPIs.

Plus one root-level artifact:

- **[`EXPERIMENTS.md`](EXPERIMENTS.md)** — append-only experiment log template. Lives at the working-dir root, gets one entry per concrete attempt. Prevents silent re-convergence on the same approach.

## How to drive Module 3 with this template

1. Symlink `data/` (whole repo data tree) and `code/` (whole repo code tree) into each agent's working dir — see [data/README.md](data/README.md) and [code/README.md](code/README.md).
2. Open the agent dir in Claude Code. `AGENTS.md` loads.
3. The agent's task prompt names the two KPIs to minimise.
4. The agent inspects skill and reference metadata first (cheap), loads bodies on demand. Recommended order in AGENTS.md.
5. Iterate: name three alternatives → pick one → fit → `scoring-model` → log to `EXPERIMENTS.md` → consult references when stuck → repeat. Use `comparing-models` for A/B. Run `pre-flighting-final-model` before declaring done.

## What's *not* here (held for later modules)

- No `tasks/` directory. The KPI brief lives in the agent's run-time prompt, not in the template.
- No `evals/` directory. Skill-level evals appear in later modules.
- No `tools/` or `.mcp/`. Empty in m3.
- No multi-agent / persona scaffolding (see "What we deliberately did *not* add" above).

## Dependencies

- Python 3.11+
- `uv` for env management (`uv sync` after first clone)
- Claude Code
