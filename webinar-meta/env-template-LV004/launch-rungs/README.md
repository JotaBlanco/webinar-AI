# launch-rungs — parallel divergent subagents

## What it is

A fan-out launcher for parallel rung-constrained subagents. At the start of a
run, the orchestrator spawns N (typically 4) isolated subagents — each with its
own context window, each constrained to a different structural rung — and lets
them work in parallel. When they return, the orchestrator picks the dev-CV
winner via `skills/iterate/` and proceeds from there.

## Why this exists

m3.v2 and m3.v3 cohorts both showed the same failure: every agent piles up on
whatever rung they started on. m3.v2 forced log-level diversity via the
`Rung: 1+` requirement, and the m3.v3 cohort *attempted* rung-1 — but every
attempt failed for the same reason (under-parameterization, see
[m4-cohort-findings.md](../references/m4-cohort-findings.md) §1 + §7).

Parallel divergent subagents address this two ways:
1. **Forced structural diversity** — the rung constraint is a launch-script
   argument, not an agent-discipline ask. Subagents can't refine away from it.
2. **Per-rung budget isolation** — each subagent gets its own wall clock, so
   the rung-1 subagent doesn't have to compete with rung-0 polish for the same
   45-min window. The m3.v3 cohort §1 budget pressure (agent-03 couldn't
   converge rung-1 on IONIQ in 45 min) goes away when the rung-1 subagent has
   30 min all to itself.

Source for the broader pattern: Anthropic's multi-agent research architecture
(orchestrator-worker with context-isolated subagents — 90.2% lift on internal
eval); MAESTRO divergent-convergent (arXiv 2511.06134); the structured
divergence finding in arXiv 2509.22480.

## Files

- [`manifest.yaml`](manifest.yaml) — declarative list of subagents. Default
  ships 4: rung-0 polish, rung-0 orthogonal (residual learner), rung-1
  dynamic-ST fit, rung-1 regime-switched. Edit freely.
- [`launch.sh`](launch.sh) — shell driver. Generates per-subagent prompts
  and spawns true OS-level parallel `claude` CLI sessions. Use when driving
  from a shell terminal outside Claude Code.
- [`orchestrate.md`](orchestrate.md) — Task-tool dispatch protocol. Use when
  driving from inside an open Claude Code session (orchestrator role).
- `_sessions/` — per-subagent workdirs containing their generated `PROMPT.md`
  and per-session logs. Inspectable after a run.

## Two dispatch paths, same outcome

Pick based on where you're driving from:

| You are driving from… | Use |
|---|---|
| Shell terminal, outside Claude Code | `bash launch.sh` |
| An open Claude Code session (orchestrator) | [`orchestrate.md`](orchestrate.md) |
| A non-Claude harness (Quix runtime, custom SDK) | `bash launch.sh --dry` to generate prompts, then adapt |

`launch.sh --dry` writes the per-subagent `PROMPT.md` files without spawning
sessions — useful both for inspection and as the input to `orchestrate.md`'s
Task-tool dispatch.

## When NOT to use parallel fan-out

The only valid reason to skip parallel fan-out in m4.v1.01 is **the
environment cannot spawn parallel sessions** (no Claude Code CLI, single
machine without process isolation). Budget is not a reason — the
orchestrator has 90 minutes and each subagent has 45–60.

If your environment forces sequential execution, run the 6 subagents one at
a time, with their rung constraints intact. The structural-diversity
argument still holds; you give up the wall-clock benefit but keep the most
important property — mechanically-enforced rung diversity. The `iterate`
skill works the same way either way.

Document the skip in REPORT.md § "Process deviations" so the next cohort
knows the environment didn't allow parallelism (vs the agent deciding to
skip).

## Persona is not a rung

This is **context isolation**, not role-play. Every subagent uses the same
underlying skills, the same references, the same operating contract. The
*only* thing that differs is the structural starting point and the budget.
Persona / multi-role multi-agent ("yaw specialist + CTE specialist") is
explicitly out of scope and was ruled out for the same reasons m3.v2 ruled it
out (Cognition, Wasowski, Anthropic production patterns 2026).
