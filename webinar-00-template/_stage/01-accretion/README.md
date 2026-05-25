# _stage/01-accretion

Substrate-as-protagonist angle. Audience watches one substrate accrete one layer per module across 30 minutes; same agent, same question, four progressively better answers, every delta in a `git diff`.

Full proposal: [`../../../KB002/ai-axis/ai-axis-ideas/01-knowledge-accretion/proposal.md`](../../../KB002/ai-axis/ai-axis-ideas/01-knowledge-accretion/proposal.md).

## How to drive the substrate

The root substrate is in its workshop-end state. For this angle, *erase back to nothing* and grow live.

### M1 start state — empty lamp

- `AGENTS.md` truncated to 3 lines (project name + build cmd + lint cmd; **no** glossary, **no** known traps).
- `skills/` emptied (real skills moved to `skills.workshop-end-reference/`).
- MCP servers live but the agent has no skill to guide their use.
- Inspector running in the corner pane (borrow from `_stage/02-empathy/inspector/`).

### Module-by-module substrate target

| After module | `AGENTS.md` | `skills/` | `evals/` |
|--------------|-------------|-----------|----------|
| M1 (empty lamp) | 3 lines | empty | empty |
| M2 (ratchet) | ~25 lines (units glossary + 1 known trap that just bit) | empty | empty |
| M3 (crystallise) | same | first skill, just-authored | empty |
| M4 (sensor + self-patch) | same | first skill, self-patched | first eval |
| (close) | git diff M1..M4 slide | | |

## Load-bearing stage discipline

- Every module **must** end with `git diff` of the substrate visible on screen. If a module's substrate didn't change, the module didn't earn its slot.
- The inspector (corner pane) should run the *whole* 30 minutes so the audience can read two axes at the close: file-tree growth + per-turn-cost shrinkage on the same question.
- Honest caption at M4: *"5 iterations compressed to 2 on stage."* Do not drop under time pressure.
