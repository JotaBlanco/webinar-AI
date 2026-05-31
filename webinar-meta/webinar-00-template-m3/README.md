---
title: webinar-00-template-m3 — Module 3 substrate (skills + references)
summary: Module-3 template for the lateral-fidelity webinar. Same seven-skill toolkit and shared math library as m2, plus three short domain-knowledge reference documents (anti-patterns, approach-menu, two-kpi-tradeoff) that name the levers prior cohorts missed. The references are the m3 increment over m2 — everything else is identical.
tags: [template, webinar, m3, skills, references, lateral-fidelity]
updated: 2026-05-31
---

# webinar-00-template-m3

Module 3 substrate for the lateral-fidelity webinar. **The m3 increment over m2 is the `references/` directory** — three short markdown files that name the misframes prior cohorts talked themselves into. Skills, AGENTS.md framing, `_shared/` math, and the operating contract are identical to m2.

This README is for the human setting up the template. The agent reads [AGENTS.md](AGENTS.md) — that's the authoritative source for the working-directory layout, the skills inventory, the references inventory, and the modify-the-skill protocol. Don't duplicate that content here.

## Design principles (carried forward from m2)

Informed by the m1+m2+m3 cohort grade at `_grade/20260531-003104/`:

1. **Diagnostic surface, not polished oracle.** `scoring-model` returns per-segment tables, per-platform signed bias, bias-vs-noise decomposition, per-route pooling, worst-N outliers, distributions, plus a `format_summary` dashboard — not a single pooled number.
2. **Skills as clay, not library.** SKILL.md prose pushes hard on "edit the body if the output isn't useful". Skills are short on purpose.

## What m3 adds — the references layer

Three short markdown documents under [`references/`](references/):

- **`anti-patterns.md`** — common ways prior work has gone wrong. Names the per-segment-bias-removal trap, the fit-on-one-platform mistake, the sample-level train/dev leak.
- **`approach-menu.md`** — a map of the option space for improving on V0, annotated by what's been explored and what hasn't.
- **`two-kpi-tradeoff.md`** — how yaw-rate RMSE and CTE RMSE relate. What it means when a model wins one and loses the other.

The grading diagnosis showed these three documents — *just three markdown files, no new code* — closed the entire +12 pp CTE gap between m2 and m3 cohorts. The references are the substrate-level addition that m3 ships.

## How to drive Module 3 with this template

1. Symlink `data/` (whole repo data tree) and `code/` (whole repo code tree) into each agent's working dir — see [data/README.md](data/README.md) and [code/README.md](code/README.md).
2. Open the agent dir in Claude Code. `AGENTS.md` loads.
3. The agent's task prompt names the two KPIs to minimise.
4. The agent inspects skill and reference metadata first (cheap), loads bodies on demand.
5. Iterate: fit, `scoring-model`, read the per-platform signed bias, consult `references/two-kpi-tradeoff.md` when interpreting, modify the model. Use `comparing-models` for A/B. Run `pre-flighting-final-model` before declaring done.

## What's *not* here (held for later modules)

- No `tasks/` directory. The KPI brief lives in the agent's run-time prompt, not in the template.
- No `evals/` directory. Skill-level evals appear in later modules.
- No `tools/` or `.mcp/`. Empty in m3; if the project gains MCP servers later, add them then.

## Dependencies

- Python 3.11+
- `uv` for env management (`uv sync` after first clone)
- Claude Code
