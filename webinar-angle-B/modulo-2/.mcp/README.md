# .mcp

MCP (Model Context Protocol) server configs. One JSON per server. Claude Code reads these at session start.

## When to add an MCP server

When a tool surface is large enough that direct shell-out (Claude Code's Bash/Python tool) becomes awkward — typically when you have:
- a related set of tools that share state (e.g. a connection pool to a data store)
- a tool surface you want to share across multiple agents or sessions
- a connectivity layer that benefits from a structured contract

For one-off tools, the direct-call pattern (just put a script in `tools/`) is simpler. **The MCP-vs-direct-call decision is the same shape as NC-10's MCP-vs-skill split — MCP is for connectivity, skills are for judgement.**

## When NOT to add an MCP server

- The hello-world smoke test. Direct shell-out is fine.
- A single tool used by a single skill. Just put it in `tools/`.

## Files

- `example-server.json` — placeholder spec showing the shape. Not wired up; the hello-world demo does not use MCP.
