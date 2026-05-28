# Observations log

Notes from running the same lateral-fidelity challenge across the 4 module substrates of angle-B (context engineering empathy arc).

## Setup

- Same challenge.md in `modulo-{1..4}/tasks/challenge.md`.
- Same code (symlinked) and same data (symlinked).
- Each agent is told its world is `modulo-N/ + code/ + data/`, nothing else.
- Agents run sequentially. After each, observations are logged here.

## Hypothesis

- M1 should struggle: bloated AGENTS.md eats per-turn tokens; no skills/references; the agent has to discover code structure from scratch.
- M2 should struggle similarly or worse (more bloat from CLAUDE.md), but we observe what slips.
- M3 should be cleaner: lean AGENTS.md + on-demand skills + references. Agent ramps up faster.
- M4 should be the most disciplined: forced into RPI loop, fresh-context discipline.

## Per-module observations

- [m1-observations.md](m1-observations.md)
- [m2-observations.md](m2-observations.md)
- [m3-observations.md](m3-observations.md)
- [m4-observations.md](m4-observations.md)

## Cross-module synthesis (after all 4)

- [synthesis.md](synthesis.md) (TBD)
