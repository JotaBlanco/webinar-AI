# AGENTS.md — TEMPLATE

> Replace this file with your project's substrate. Every line below is a placeholder — keep the *shape*, swap the *content*.
>
> Discipline: every line of a real AGENTS.md should be traceable to a past failure. Don't speculate. Start short. Grow only when something breaks.

## Project purpose

TODO — one paragraph. What does this project do, and what does it deliberately *not* do? The agent reads this first; it sets the boundary of "is this task in scope?"

## Build / run

- TODO — environment setup (`uv sync` / `npm install` / whatever).
- TODO — how to run a smoke test (`uv run python -m skills.hello_world` if you keep hello-world Python-flavoured).
- TODO — how to invoke a skill end-to-end.

## Units and conventions

> Replace with your domain's units and conventions. Every line below should be a real convention your team uses; every one should be a guard against a real mistake.

- TODO — units (SI? Mixed? Imperial in any field?). State explicitly.
- TODO — coordinate frames / sign conventions / time bases.
- TODO — naming conventions for signals, parameters, files.

## Known traps

> The most important section. Every entry below is a past failure mode the team has hit and engineered out *here* rather than in N skill files. Add one line per failure.

- TODO — the first trap you remember from a past project.
- TODO — the second.

## Skills inventory

The agent should inspect a skill's metadata before deciding to load its body. Never load all skill bodies eagerly. See [`skills/`](skills/).

- `hello-world/` — smoke-test skill for verifying the harness loads correctly. Delete after first real skill is authored.
- TODO — your first real skill.

## Evals

[`evals/`](evals/) contains computational sensors (deterministic checks). A skill's output is only valid if the matching eval passes. See [`evals/README.md`](evals/README.md).

## References

[`references/`](references/) holds domain docs the agent loads on demand — schemas, glossaries, standards. Usually accessed via a reference-style skill, not loaded into AGENTS.md.

## MCP servers

[`.mcp/`](.mcp/) holds MCP server configs. Claude Code reads these at session start. Servers handle *connectivity*; skills handle *judgement* (NC-10).
