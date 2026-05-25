# Módulo 1 — Bare harness

Components present:
- **Tools (1)** — `tools/` (3 wrappers).
- **Context-seed (3)** — `CLAUDE.md` (raw braindump).

Components absent:
- Memory/State (2) — no `AGENTS.md`.
- Planning (4) — no RPI templates.
- Verification (5) — no `evals/`.
- Modularity (6) — no `skills/`.

The agent is expected to limp. That is the lesson — every later module adds one component and the audience sees a specific kind of failure stop recurring.

Run: `python tools/list_segments.py`, etc. Outputs land in `out/`. Do not write to `data/` or modify `code/` in place.
