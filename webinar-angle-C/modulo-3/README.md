# Módulo 3 — + Planning + Verification

Components present:
- **Tools (1)**, **Memory/State (2)**, **Context-seed (3)**.
- **Planning (4)** — `rpi/` (RPI loop: research → plan → implement with locked artifacts).
- **Verification (5)** — `evals/` (two computational sensors + one inferential judge spec).

Components absent:
- Modularity (6) — no `skills/`.

The point of module 3: the agent that handled M2's challenge ad-hoc now must **plan in writing before implementing**, and any output that doesn't pass the computational sensors is invalid. Failure modes that M2 still hit (e.g. plausible-looking but wrong baseline numbers, ablation that conflates two changes) should now stop recurring.

Read `AGENTS.md`, then `rpi/RPI_INSTRUCTIONS.md`, then the challenge. Outputs in `out/`.
