# M2 — observations

## Run summary
- Duration: ~3.9 min (234s) — *faster* than M1
- Total tokens: ~48k — *slightly fewer* than M1
- Tool uses: 14 — *fewer* than M1's 18
- REPORT.md: written
- Isolation: respected

## What worked
- Built 5 cumulative variants: baseline → +bias → +steer cal → +understeer → +lag.
- Best result: F-150 **−63% RMSE ψ̇** (1.104 → 0.413 °/s). Better than M1's −47%.
- Mach-E also improved: 0.505 → 0.394 (−22%).
- Reproducer in `ablation.py`.
- Honest about in-sample-only calibration (no held-out split).

## What slowed the agent down
1. **Write tool refused to write `REPORT.md`** — the agent reports "subagents should return findings as text". Fell back to `cat > REPORT.md <<EOF` via Bash. Tool-use friction, not substrate friction. (Note for orchestrator: if this is reproducible, our final-deliverable contract conflicts with the Agent tool's default guidance.)
2. **No CAN-decode deps** (same as M1).
3. **Only 2 segments per platform** — wanted a held-out split (same as M1).

## My observations as orchestrator

**Surprise: M2 outperformed M1.** Counter to the empathy-arc hypothesis that "more bloat = worse outcome". Why?

The CLAUDE.md dump in M2 *included operational information that M1 had to discover from scratch*: the CSV column layout, the speed-known operating contract, the file structure of `code/`. M1's agent had to grep + read to find these; M2's agent had them on a plate. The "tax" of CLAUDE.md being reloaded every turn never materialised because the run was short (14 tool uses, 48k total tokens — nowhere near the 40% context cliff).

**This is the key empirical finding for the workshop angle:**
- The 944-vs-53 / smart-warm-dumb lesson is **about long-running sessions**, where per-turn AGENTS.md cost compounds.
- In a **short single-turn agent run**, MORE context (even messy context) helps more than it hurts. The bloat doesn't degrade the agent because it doesn't run out of capacity.
- For a live workshop demo, **this matters**: a single short run can't honestly show the smart→warm→dumb degradation. The demo needs to either (a) artificially extend the session (interactive, many turns), or (b) instrument per-turn cost (the inspector) so the audience SEES the tax even on a short run, even though the agent doesn't FEEL it.

**Tool-call efficiency tells a different story than RMSE:**
- M1: 18 tool uses, ~261s, baseline 0.416/1.061 °/s, best −47%
- M2: 14 tool uses, ~234s, baseline 0.505/1.104 °/s, best −63%
- M2 was more efficient (fewer turns, less time) AND got further on the modelling. The CLAUDE.md dump was a *net win* for substrate quality at this scale, even though it's "messy" by Horthy/Shimeles standards.

The lesson the workshop will actually demonstrate, if M3 is faster/better still, is: **well-organised on-demand substrate beats both extremes** (M1's empty-and-discover OR M2's dump-it-all). Let's see if M3 confirms this.

## Slight baseline differences M1 vs M2
- Mach-E: 0.416 (M1, mean-of-segments) vs 0.505 (M2, pooled). Same data, different aggregation. Pooled gives more weight to longer segments. Both valid.
- F-150: 1.061 vs 1.104. Same comment.
- The variant *improvements* are comparable in magnitude; the difference in baseline is just methodology.
