# Synthesis — angle B (context-engineering empathy arc), first dry run

## What we tested
The same lateral-fidelity challenge ("improve the KS model's lateral fidelity, quantify each addition") given to 4 agents, each in a progressively-better substrate:

- **M1**: bloated AGENTS.md (~900-token vehicle-dynamics conventions block + generic agent boilerplate), no skills, no CLAUDE.md.
- **M2**: M1 + a naive CLAUDE.md dump (KB layout, operating contract, CSV schema — useful info but unstructured, paid every turn).
- **M3**: lean AGENTS.md + 2 on-demand skills (`vehicle-dynamics-rlog`, `sim-real-runtime`) loaded metadata-first.
- **M4**: M3 + RPI scaffolding (forced Research → Plan → Implement across artifacts).

## Results table

| Module | Tokens | Tools | Duration | F-150 best ψ̇ | Mach-E best ψ̇ |
|---|--:|--:|--:|--:|--:|
| M1 | 50k | 18 | 4.4 min | −47% | −1% |
| M2 | 48k | 14 | 3.9 min | −63% | −22% |
| M3 | **59k** | **23** | **4.9 min** | **−68%** | **−82%** |
| M4 | 76k | 33 | 8.6 min | −51% | −76% |

## Findings that confirm the angle's hypotheses

1. **Skills (M3) deliver the best numerical result on the task that wants depth, not breadth.** The `vehicle-dynamics-rlog` skill's "fidelity ladder" section explicitly names ST with β-state; M3 implemented exactly that, where M1/M2 stopped at closed-form approximations. This is the workshop's NC-12 (progressive disclosure) claim landing empirically: pay tokens *for* the right thing, *when* it's needed.

2. **The on-demand loading worked**. M3's agent did not preload skills — it loaded their bodies in phase order (sim-real-runtime first to ground the workspace, vehicle-dynamics-rlog second when diving into model improvements). That is the architecture in action.

3. **The RPI loop produces the best analytical artifacts** (M4's `research.md` is the cleanest per-segment diagnosis of the four). On a task where the deliverable is the *thinking*, this would have been worth it.

## Findings that complicate the angle's hypotheses

1. **M2 outperformed M1 on the metric, despite "more bloat".** Adding the CLAUDE.md dump (~600 extra tokens per turn) helped more than it hurt on a *short, single-turn-shaped* agent run. The 944-vs-53 / smart-warm-dumb cliff is a *long-session* phenomenon. None of our 4 runs got near the 40% fill threshold (the highest was M4 at ~75k tokens, well below 200k working ceiling).

   **Implication for the workshop**: a single short demo cannot honestly land the "context fill kills the agent" beat. The demo needs to either (a) be a long interactive session, or (b) be instrumented with the inspector so the *per-turn cost* is visible even when the cliff isn't hit. The proposal already calls for the inspector — this confirms it is the load-bearing prop.

2. **M4 underperformed M3 numerically.** RPI's plan-lock made the agent conservative (it chose H3 over H2 because H2 was "too risky inside time budget"). M3, free to swing, implemented dynamic ST and won. *On a short cheap-iteration task, the RPI discipline guard-rails away from high-upside bets.* On a brownfield production task this would be the right behaviour — but the workshop must not pretend RPI is monotonic improvement. The honest claim is: **RPI shifts the variance**, it does not always shift the mean upward.

3. **The "computer in the dark" effect was not visible in a single short run.** M1's agent succeeded at the task — slower, with a worse result, but it did not "fail". The 944-token AGENTS.md never accumulated into observable degradation. The visceral M1 beat in the workshop will need to be staged differently: not "the agent fails" but "look how much the agent had to spend tokens discovering things that should have been on the substrate."

## What the agents themselves wished for (the shadow substrate gap list)

Same three items came up across multiple modules — these are NOT substrate problems, they're environment problems:

1. **More segments** (n=2 per platform makes generalisation untestable). Mentioned by M1, M2, M3, M4.
2. **CAN-decode deps** (cantools/pycapnp/zstandard). Mentioned by M1, M2, M4. Blocks any improvement that touches the rlog→input pipeline.
3. **Tool friction on REPORT.md write** (subagent harness intercepts Write for markdown). Mentioned by M2, M3, M4. Reproducible.

The agents asked for none of these inside the substrate. They asked for them in the *environment*. The workshop's M1 emotional beat can be sharpened by deliberately surfacing this dichotomy: *some things belong in the harness (AGENTS.md, skills) — but some belong outside it (deps, data depth, tooling). Confusing the two is itself a substrate-engineering mistake.*

## What worked about this experiment design

- The isolation contract was respected by all 4 agents — none accessed paths outside their allow-list, despite all being run from the same parent CWD. The prompt-level instruction was sufficient (no filesystem sandbox needed).
- Sequential running (M1 → M2 → M3 → M4) let us catch the env issues (CAN deps missing) early without contaminating the substrate evaluation.
- Pre-existing sim CSVs unblocked the agents from needing to regenerate (which would have failed on the deps issue).

## What didn't work / would change next iteration

- **The run was too short to surface the context-fill cliff.** Need a deliberately verbose multi-turn task — or a per-turn cost meter — for the empathy beat to land.
- **n=2 segments per platform** was the agents' biggest complaint. Adding even 3-5 more segments per platform would make the generalisation-vs-overfit conversation possible.
- **Tool friction on REPORT.md** needs to be resolved before the workshop — the agent should not have to fall back to `cat << EOF` to write a deliverable artifact.
- **The progression M1 → M2 should be reconsidered.** If "M2 = M1 + more naive bloat" doesn't degrade outcomes on a short run, the M2 demo loses force. Better M2 framing: introduce the inspector itself (so the audience SEES the per-turn cost go up *without* the agent failing). The teaching moment is not "M2 agent failed" — it's "M2 paid 2× the tokens for the same outcome".

## Recommended next experiments (if the user wants to keep iterating)

1. **Add 5-10 more Ford segments** to the data tree, ensuring at least a few have meaningful lateral content (|a_y| > 2 m/s²). Re-run all 4 modules.
2. **Force a longer task** that requires multiple iterations (e.g. "implement and stress-test 4 separate hypotheses, each with its own evaluation"). This should surface the M1 dark-room pain more visibly.
3. **Implement the inspector** (`_stage/02-empathy/inspector/context_window_inspector.py` in the template). Log per-turn cost during each run so we have an empirical curve to overlay.
4. **Try the M2 framing variant** where M2 ADDS the inspector instead of adding more bloat. Test whether the inspector alone (without substrate change) gives M2 a meaningful identity vs M1.
