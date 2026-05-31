# _stage/04-author

Domain-expert-as-skill-author angle. The workshop driver (in persona) authors a real domain skill live on stage; a second skill is pre-baked off-stage following the same loop and dropped in at M4.

Full proposal: [`../../../KB002/ai-axis/ai-axis-ideas/04-domain-expert-skill-author/proposal.md`](../../../KB002/ai-axis/ai-axis-ideas/04-domain-expert-skill-author/proposal.md).

## How to drive the substrate

M1 start state: *normal AGENTS.md, empty `skills/`*. The driver walks the agent manually through a real domain task; the skill emerges from the walk.

### Module-by-module substrate target

| After module | `skills/` state |
|--------------|-----------------|
| M1 (walking the workflow) | empty; annotated transcript saved at `_stage/04-author/transcripts/m1-walk.md` |
| M2 (crystallise) | first skill at v0.1 — works on the easy half, breaks on the second case |
| M3 (self-improve + sensor) | same skill at v0.5 (visible markdown diff across 2 iterations); first eval wired as regression guard |
| M4 (compose) | `+` second pre-baked skill dropped in; agent solves the compound question using both |

## Pre-baked artifacts (this folder)

- `transcripts/m1-walk.md` *(to add)* — pre-rehearsed transcript of the M1 manual walk. Used as fallback if the live walk goes off-rails past 60 s.
- `pre-baked-second-skill/<name>/` *(to add)* — the second skill, authored off-stage following the M1–M3 loop, ready to drop into `skills/` at M4.

## Load-bearing discipline

- The driver must stay in the *domain expert* seat, not the *software engineer* seat. M1's walk is in your domain's vocabulary, never in agent-framework vocabulary. If you code-switch into harness internals on stage, the org-chart-inversion thesis collapses (that lives in angle 03, not here).
- Honest caption at M3 — *"5 iterations compressed to 2 on stage"* — must not be dropped under time pressure. This is the inoculation against "looks too easy".
- Pick a skill where the *validate* half is the load-bearing word — validation is where domain judgement lives, which is where the skill earns its keep.
