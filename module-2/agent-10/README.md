---
title: webinar-00-template-m2 — Module 2 starter substrate (skills toolkit)
summary: Module-2 template for the lateral-fidelity webinar. Ships with seven small, modifiable skills plus a shared math library. The agent gets a richly diagnostic scoring oracle, a residual-vs-feature plotter, route-grouped train/dev split with a leakage validator, and a deliverable-contract preflight. Module-3+ domain references are deliberately absent — those land in their own templates.
tags: [template, webinar, m2, skills, lateral-fidelity]
updated: 2026-05-31
---

# webinar-00-template-m2

Module 2 substrate for the lateral-fidelity webinar. Skills are designed to **widen exploration** rather than funnel every agent to the same answer.

This README is for the human setting up the template. The agent reads [AGENTS.md](AGENTS.md) — that's the authoritative source for the working-directory layout, the skills inventory, and the modify-the-skill protocol. Don't duplicate that content here.

## Design principles

Informed by the m1+m2+m3 cohort grade at `_grade/20260531-003104/`:

1. **Diagnostic surface, not polished oracle.** `scoring-model` returns per-segment tables, per-platform signed bias, bias-vs-noise decomposition, per-route pooling, worst-N outliers, distributions, plus a `format_summary` dashboard — not a single pooled number.
2. **Skills as clay, not library.** SKILL.md prose pushes hard on "edit the body if the output isn't useful". Skills are short on purpose.
3. **No domain-knowledge references in M2.** Anti-patterns / approach menus / KPI-tradeoff docs are held for Module 3+ on purpose.

## How to drive Module 2 with this template

1. Symlink `data/` (whole repo data tree) and `code/` (whole repo code tree) into each agent's working dir — see [data/README.md](data/README.md) and [code/README.md](code/README.md).
2. Open the agent dir in Claude Code. `AGENTS.md` loads.
3. The agent's task prompt names the two KPIs to minimise.
4. The agent inspects skill metadata first (cheap), loads bodies on demand.
5. Iterate: fit, `scoring-model`, read the per-platform signed bias, modify the model. Use `comparing-models` for A/B. Run `pre-flighting-final-model` before declaring done.

## What's *not* here (held for later modules)

- No `references/` directory with domain knowledge (per-segment derivations, anti-patterns, KPI tradeoffs). These live in Module 3+.
- No `tasks/` directory. The KPI brief lives in the agent's run-time prompt, not in the template.
- No `evals/` directory. Skill-level evals appear in later modules.
- No `tools/` or `.mcp/`. Empty in M2; if the project gains MCP servers later, add them then.

## Dependencies

- Python 3.11+
- `uv` for env management (`uv sync` after first clone)
- Claude Code
