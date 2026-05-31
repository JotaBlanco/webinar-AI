---
title: webinar-00-template — reusable substrate template
summary: Folder-structure template for spinning up a domain-specific webinar demo repo that can drive four of the five AI-axis workshop angles (01 accretion, 02 empathy, 04 author, 05 experiment). Lean / flat / Python-flavoured. Replace the hello-world skill + sample task with your own domain content. Angle 03 (six-component harness-as-product) is not supported and would need a different layout.
tags: [template, webinar, substrate, ai-axis, harness]
updated: 2026-05-20
---

# webinar-00-template

Template for a single-project demo repo. Each real webinar gets its own copy (`webinar-01`, `webinar-02`, …) with domain content swapped in.

## How to adapt the template

1. **Copy** this folder to `webinar-NN-<short-name>` (e.g. `webinar-02-thermal-bridge`).
2. **Verify the wiring** with the included hello-world skill — open the repo in Claude Code, ask the question in [`tasks/hello.md`](tasks/hello.md), confirm the agent loads the skill, reads `data/example.csv`, returns a sensible answer, and that `evals/hello_world_eval.py` passes on its output.
3. **Replace the hello-world skill + sample data + sample task** with your domain content. See "What to fill in" below.
4. **Pick a workshop angle late** — see [`_stage/`](_stage/) for one folder per supported angle, each with a README explaining how to drive the substrate for that narrative.

## Layout

| Folder | Holds | Who reads / writes |
|---|---|---|
| [`AGENTS.md`](AGENTS.md) | The harness substrate — units, conventions, known traps, skills inventory. Every line traceable to a past mistake. | Agent reads every turn; team writes |
| [`skills/`](skills/) | `SKILL.md` folders — procedural recipes the agent loads metadata-first. One subfolder per skill. | Agent reads on demand; domain expert writes |
| [`tasks/`](tasks/) | The questions of the day. One markdown per question. | Agent reads; team writes |
| [`data/`](data/) | Raw observations, traces, drawings, measurements — anything the agent reads as input. Convention: `raw/`, `processed/`, `fixtures/`. | Agent reads (usually via tools or MCP) |
| [`code/`](code/) | The project's own implementation — model, calculator, analyzer. The thing that already exists in the engineering team. | Agent reads; tools import from here |
| [`tools/`](tools/) | Thin wrappers exposing `code/` (or `data/`) to the agent via direct call or MCP. | Agent calls |
| [`references/`](references/) | Domain docs, schemas, glossaries, standards. Loaded on demand via a reference-style skill. | Agent reads on demand |
| [`evals/`](evals/) | Computational sensors — deterministic checks that score a skill's output. Used by angles 01 and 04. | Agent or CI calls |
| [`.mcp/`](.mcp/) | MCP server configs. One JSON per server. | Claude Code reads at session start |
| [`_stage/`](_stage/) | Angle-specific tooling. One subfolder per supported workshop angle. | Workshop driver runs |

## What to fill in (in order)

1. **`AGENTS.md`** — replace the TODOs with your project's purpose, build/run commands, units glossary, known traps. Every line should be traceable to a past failure once the project is live.
2. **`tasks/`** — the question(s) of the day. Make at least one *concrete* (named artifact, named magnitude, falsifiable). See [`tasks/hello.md`](tasks/hello.md) for the shape.
3. **`skills/<your-first-skill>/SKILL.md`** — author the first real skill via the walk-then-crystallise loop (NC-18). Use [`skills/hello-world/SKILL.md`](skills/hello-world/SKILL.md) as the shape reference.
4. **`code/`** — drop in your domain code (any language). The README explains how `tools/` wrappers expose it to the agent.
5. **`tools/`** — write one wrapper per primitive operation the agent needs to call. Either directly (Claude Code Bash/Python tool) or via an MCP server defined in `.mcp/`.
6. **`data/fixtures/`** — small, version-controlled subset of `data/raw/` used for demos and evals.
7. **`evals/`** — one `<skill-name>_eval.py` per skill that needs a sensor. See [`evals/hello_world_eval.py`](evals/hello_world_eval.py) for the contract.
8. **`references/`** — any domain doc the agent should load on demand. Often a "schema" or "glossary" reference skill points here.

## Pick a workshop angle

Five angles were considered in [`../KB002/ai-axis/ai-axis-ideas/`](../KB002/ai-axis/ai-axis-ideas/). This template supports four of them via [`_stage/`](_stage/):

| Angle | One-liner | Substrate state at M1 |
|---|---|---|
| 01 accretion | Substrate grows live, one layer per module | empty AGENTS.md, empty `skills/` |
| 02 empathy | Context-window inspector is the centrepiece | bloated AGENTS.md, 2 pre-authored skills |
| 04 author | Domain expert authors a skill live | normal AGENTS.md, empty `skills/` |
| 05 experiment | Same question, 4 scaffolds, controlled comparison | normal end-state + 4 scaffolds |

Angle 03 (harness-as-product, six BettaTech components) diverges enough that it would need a different scaffold; it is not supported here.

## Dependencies

- Python 3.11+
- `uv` for env management (`uv sync` after first clone)
- Claude Code (the CLI / IDE extension) for the on-stage agent harness

The Python flavouring is a convention, not a hard requirement — `code/` and `tools/` can be any language. The hello-world demo + the inspector stub + the example eval are Python; replace with whatever your project uses.
