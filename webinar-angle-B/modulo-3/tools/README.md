# tools

Thin wrappers that expose `code/` and `data/` to the agent. Each tool is one primitive operation with a clear signature, a docstring the agent will read, and as little logic of its own as possible.

## What goes here

- Wrappers that call into `code/` and return a structured result.
- Data loaders that read from `data/` and return summaries (not raw 100 Hz dumps — those blow up context).
- Anything the agent invokes directly (via Claude Code's Bash/Python tool) or indirectly (via an MCP server defined in `.mcp/`).

## What does NOT go here

- Domain logic — that lives in `code/`. `tools/` imports from `code/`, never reimplements.
- Skills — those are `SKILL.md` files under `skills/`. Tools are *primitives*; skills are *procedures* that compose primitives.

## Two patterns for exposing tools to the agent

1. **Direct call** — Claude Code's built-in Bash/Python tool runs the script. Cheapest, simplest. Use when the tool is local-only and the agent is trusted to invoke it.
2. **MCP server** — a server in `.mcp/` exposes a typed tool surface. Use when the tool needs to be sharable across agents / sessions, or when the connectivity layer benefits from a structured contract (NC-10 — *MCP for connectivity, skills for judgement*).

The hello-world demo uses the direct-call pattern (no MCP needed). The `.mcp/example-server.json` shows the shape for when you add one.

## Tool contract

Every tool module should expose at least one function with:
- a docstring the agent will read (this *is* the tool description in the model's context)
- typed arguments
- a return value that's either a primitive or a small dict — never a large array or DataFrame

## Template state

- `example_tool.py` — provides `compute_stats(file_path)` used by the hello-world skill. Replace with your domain tools.
