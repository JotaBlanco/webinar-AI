---
title: webinar-00-template-m2.v2 — Module 2 starter substrate (skills toolkit)
summary: Module-2 template for the lateral-fidelity webinar. Ships with six small, modifiable skills plus a shared math library. The agent gets a richly diagnostic scoring oracle, route-grouped train/dev split with a leakage validator, and a deliverable-contract preflight. Module-3+ domain references are deliberately absent — those land in their own templates.
tags: [template, webinar, m2, skills, lateral-fidelity]
updated: 2026-05-31
---

# webinar-00-template-m2.v2

Successor to `webinar-00-template-m2`. Same purpose — drive Module 2 of the lateral-fidelity webinar — but with skills redesigned to **widen exploration** rather than funnel every agent to the same answer.

The lessons that drove v2 (see the diagnosis on the m1+m2+m3 cohort grade `_grade/20260531-003104/`):

1. **Diagnostic surface, not polished oracle.** v1's `score-model` returned a pooled CTE number and let agents climb the yaw hill. v2's returns per-segment tables, per-platform signed bias, bias-vs-noise decomposition, per-route pooling, worst-N outliers, distributions, plus a `format_summary` dashboard.
2. **Skills as clay, not library.** v1 agents (0/10) modified any skill. v2 SKILL.md prose pushes harder on "edit the body if the output isn't useful".
3. **No domain-knowledge references in M2.** Anti-patterns / approach menus / KPI-tradeoff docs are held for Module 3+ on purpose.

## Layout

| Path | Holds |
|---|---|
| [`AGENTS.md`](AGENTS.md) | The always-on substrate — folder layout, skills inventory, modify-the-skill framing. ~30 lines. |
| [`skills/`](skills/) | Six skill folders, each with `SKILL.md`, body code, and `_smoke.py`. |
| [`_shared/`](_shared/) | Local trajectory-math library (`traj_metrics.py`). The agent's own copy — not linked to the canonical grader. |
| [`code/`](code/) | Symlinked baseline model code, including `ks_model.py` (read-only). |
| [`data/`](data/) | Symlinked sim data tree (read-only). |
| [`_stage/`](_stage/) | Angle-specific tooling per supported workshop angle. |

## Skills inventory (all use gerund-form names per Anthropic's routing guidance)

| Skill | Type | Role |
|---|---|---|
| `loading-segments` | pure infra | Load `sim.csv` files with consistent dtypes and parsed path metadata. |
| `making-train-dev-split` | infra + validator | Route-grouped train/dev split. Ships with `validate_split.py` that raises on leakage / collisions. |
| `scoring-model` | inner-loop oracle | Headline KPIs + per-segment table + per-platform signed bias + bias fraction + per-route + worst-N + distributions + dashboard. |
| `comparing-models` | A/B diagnostic | Per-segment diff; `top_regressions` / `top_improvements` / `per_platform_summary` / `format_summary`. |
| `inspecting-residuals` | diagnostic plotter | Yaw residual vs any input feature, per-platform binned mean ±1σ. Use to discover which input dimension explains a bias surfaced by scoring-model. |
| `visualising-segment` | one-shot plotter | 3-panel PNG (bird's-eye / yaw vs time / residual). |
| `pre-flighting-final-model` | deliverable validator | Verifies the `final-model/` bundle matches the contract — predicts on one real segment end-to-end. |

## How to drive Module 2 with this template

1. Symlink `data/sim/` and `code/ks_model.py` into the working directory.
2. Open the repo in Claude Code. AGENTS.md loads.
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

## Pick a workshop angle

This template is angle-agnostic substrate. Angle-specific tooling is wired in [`_stage/`](_stage/). v2 still supports the same four angles as v1 — `_stage/` contents have not been re-validated against the v2 skill set yet, so the reset scripts may need touch-up before driving an angle live.
