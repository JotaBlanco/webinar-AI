# _stage/02-empathy

Context-engineering-empathy angle. Audience learns to read the context window the way a performance engineer reads a hot loop; the inspector (this folder's `inspector/`) is the centrepiece.

Full proposal: [`../../../KB002/ai-axis/ai-axis-ideas/02-context-engineering-empathy/proposal.md`](../../../KB002/ai-axis/ai-axis-ideas/02-context-engineering-empathy/proposal.md).

## How to drive the substrate

For this angle the root substrate is loaded with a deliberately bloated block in `AGENTS.md` that gets refactored live into a skill in M3.

### M1 start state — computer in the dark

- `AGENTS.md` has the bloated block (`bloated-agents-md.md` in this folder appended to the canonical AGENTS.md) — adds ~900 tokens of domain conventions that *should* be a skill.
- `skills/` contains only the reference-style skills the agent reads on demand (e.g. schema lookups). The procedural skills are hidden.
- Inspector running, **prominently** — it is the central instrument, not a corner pane.

### Module-by-module substrate target

| After module | What moved | Inspector reads |
|--------------|------------|-----------------|
| M1 (in the dark) | nothing | session is dominated by AGENTS.md bloat |
| M2 (measurement vocabulary) | nothing; slides + a verbose-task demo crossing the 40% line | live tick from 12% to 63% on stage |
| M3 (progressive disclosure) | ~900-token block moved from AGENTS.md into a new skill | same task now stays in smart zone twice as long |
| M4 (RPI loop) | three fresh sessions; three markdown artifacts | three sawtooth traces side by side, each under 40% |

## The inspector

See [`inspector/context_window_inspector.py`](inspector/context_window_inspector.py). Stub — ~150 LOC target when implemented. The load-bearing prop. Single most-tested code in the project — *this is the demo*. Have a screen-recording fallback rehearsed.

The inspector should always print the model fingerprint (model ID + version + temperature + max-tokens) in its header line, so screenshots taken by the audience are self-documenting.

## Load-bearing discipline

- Heaviest fragility on stage. Rehearse the inspector against the exact sessions you plan to run.
- The 944-vs-53 and the 40% cliff numbers are Shimeles and Horthy respectively, on Claude. Calibrated honest answer if asked about other models: *the numbers move, the shape doesn't.*
