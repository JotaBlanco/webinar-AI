# _stage/05-experiment

Controlled-experiment angle. Same model, same question, scaffold escalates 4× (bare → workflow → universal agent + skill → RPI loop). Four answers stack at the close; the only variable is the harness.

Full proposal: [`../../../KB002/ai-axis/ai-axis-ideas/05-same-task-four-ways/proposal.md`](../../../KB002/ai-axis/ai-axis-ideas/05-same-task-four-ways/proposal.md).

## The four scaffolds

Each scaffold is a *single shell command* to start. Transitions between scaffolds are slide cuts, not live setup — keeps rehearsal cost tractable.

| # | Scaffold | Folder | Run command |
|---|----------|--------|-------------|
| S1 | Bare model | [`S1-bare/`](S1-bare/) | vanilla chat — no system prompt, no tools, no context |
| S2 | Workflow (hand-decomposed) | [`S2-workflow/`](S2-workflow/) | `uv run python S2-workflow/workflow.py` |
| S3 | Universal agent + 1 skill | the root substrate | `claude-code` in the repo root |
| S4 | Universal agent + skills + RPI | [`S4-rpi/`](S4-rpi/) | `bash S4-rpi/launch.sh` |

## The question

The same question is pasted into every scaffold (from `../../tasks/<your-question>.md`). Do not paraphrase between modules — the audience must see the input is identical.

## Load-bearing discipline

- **Same model.** Same model ID, same temperature, visible on screen each time. Use the inspector's model-fingerprint header line as the receipt.
- **Same fixtures.** All four scaffolds hit pre-staged fixtures from `../../data/fixtures/`. No network calls during the demo.
- **Token meter across all four modules.** Borrow peripherally from `_stage/02-empathy/inspector/`. Here it serves *attribution* — letting the audience see that S1 is a single blob, S2 is several tight sub-1k calls, S3 is metadata-first, S4 is three fresh sawtooth traces.

## Risk controls

- If S1 produces a defensible answer, the question is too well-represented in training data — sharpen until M1 demonstrably fails (named artifact, named magnitude).
- If S4 does not visibly beat S3, the question is too tractable for RPI to deepen — pick a question where S3 produces *correct-but-shallow* and S4's research phase surfaces a non-obvious cause.
- Rehearsal cost is the highest of the four supported angles. Each scaffold is a single shell command, but the sequencing must be drilled.
