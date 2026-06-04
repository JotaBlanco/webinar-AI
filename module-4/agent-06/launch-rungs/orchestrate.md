# Orchestrate from inside Claude Code — Task-tool dispatch

If you're driving the m4 run from *inside* a Claude Code session (rather
than from a shell), use this protocol instead of `launch.sh`. It uses the
Task tool to fan out context-isolated subagents in-process — same divergent
exploration pattern, no `claude` CLI required.

## When to use which

| You are driving from… | Use |
|---|---|
| Shell terminal, outside Claude Code | `bash launch-rungs/launch.sh` |
| An open Claude Code session (orchestrator role) | This file — Task tool dispatch |
| A non-Claude harness | `launch.sh --dry` to generate prompts, then adapt |

Both produce the same outcome: N parallel context-isolated subagents, each
writing only into its own `models/<name>/`, returning to the orchestrator
for registry merging.

## The orchestrator protocol

The orchestrator session reads `launch-rungs/manifest.yaml` and dispatches
one Task per subagent. The orchestrator does **not** do the modelling work
itself — its job is fan-out + result merge.

```
For each subagent in manifest.yaml:
    Task(
        description=f"Build rung-{rung} candidate {name}",
        subagent_type="general-purpose",
        prompt=open("launch-rungs/_sessions/<name>/PROMPT.md").read(),
    )
```

Dispatch all subagents in a **single message with multiple tool-use blocks**
so they run in true parallel. Sequential Task calls don't fan out.

Generate the per-subagent prompts first by running `bash launch-rungs/launch.sh --dry`
— that populates `launch-rungs/_sessions/<name>/PROMPT.md` without spawning
real CLI sessions, ready for the Task tool to consume.

## After fan-out — the merge step

When all Tasks return, the orchestrator:

1. Inspects each `models/<name>/predict.py` for the operating contract.
2. Runs `skills/iterate/iterate("models/<name>")` on each bundle. The skill
   handles MODELS.md / TREE.json / EXPERIMENTS.md updates.
3. Renders the tree with `skills/visualise-tree/` to see the search frontier.
4. Picks the dev-CV leader as the candidate to ship (or seeds a 2nd-round
   fan-out if the gate flags suggest a refinement is worth trying).

## Why not just have each subagent call `iterate` itself?

Subagents can read `skills/iterate/SKILL.md` for context but **must not call
it**. The iterate skill writes to shared registries — if two subagents
iterate at the same time, the registries race. The orchestrator owns the
registry merge, full stop. Subagents return *bundles*; the orchestrator
*records* them.

## Cost shape

A 4-subagent fan-out runs ~4× the tokens of a single session (one per
subagent, plus the orchestrator's overhead). That's the cost of forced
structural diversity. The cohort evidence (m3.v3 every-agent-converges-on-
rung-0 failure mode) is what justifies the spend — otherwise stay
sequential and use `iterate` directly without fan-out.

For tasks under 30 min total budget, skip fan-out. Use `iterate` in a single
session and rely on `references/m4-cohort-findings.md` to push the agent
toward orthogonal moves the cohort has already evidenced.
