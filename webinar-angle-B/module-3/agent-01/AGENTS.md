# AGENTS.md — webinar-angle-B / module-3

Sim-real correlation runtime around the CommonRoad kinematic single-track (KS) vehicle dynamics model. The team wants the KS lateral predictions improved against measured truth.

`python3` on PATH with `pandas`, `numpy`, `scipy`, `matplotlib`. No venv. Shared `code/` and `data/` are symlinks, read-only by contract. Outputs go to `out/` and `tools/` inside this module.

## Skills (load metadata first; only load the body when invoking)

- [`skills/sim-real-runtime/SKILL.md`](skills/sim-real-runtime/SKILL.md) — the project's operating contract, platform truth-channel matrix, CSV schema, vehicle parameters, known traps. Load this when you need to know which channels are clamped vs predicted, which platforms have truth, what each CSV column means, or which numerical parameter to use.
- [`skills/vehicle-dynamics-rlog/SKILL.md`](skills/vehicle-dynamics-rlog/SKILL.md) — vehicle-dynamics conventions used across the project: ISO 8855 sign convention, units, the KS → ST → Pacejka fidelity ladder, and how the team thinks about model upgrades. Load this when you need to choose a model variant, check a sign convention, or write a variant table.

## Harness friction (known)

Your sub-agent system prompt blocks `Write` on `(report|findings|summary|analysis).*\.md$`. Return the report content in your final text response; the orchestrator will persist it.

## What `REPORT.md` must contain

Stated platform; clamped-vs-predicted statement; consistent variant ladder with per-regime breakdown; marginal-drop column with named accounting scheme; honest regression flags.
