# AGENTS.md — webinar-angle-B / module-4

Sim-real correlation runtime around the CommonRoad kinematic single-track (KS) vehicle dynamics model. The team wants the KS lateral predictions improved against measured truth.

`python3` on PATH with `pandas`, `numpy`, `scipy`, `matplotlib`. No venv. Shared `code/` and `data/` are symlinks, read-only by contract. Outputs go to `out/`, `tools/`, and `rpi/runs/` inside this module.

## Workflow — RPI (Research → Plan → Implement)

Do **not** open the task and start coding. Break the work across three explicit phases using the templates in [`rpi/templates/`](rpi/templates/) and write each phase's artifact into [`rpi/runs/<timestamp>/`](rpi/runs/) before moving on. See [`rpi/README.md`](rpi/README.md) for the full discipline. The phase artifacts are part of the deliverable.

## Skills (load metadata first; only load the body when invoking)

- [`skills/sim-real-runtime/SKILL.md`](skills/sim-real-runtime/SKILL.md) — operating contract, platform truth-channel matrix, CSV schema, vehicle parameters, known traps.
- [`skills/vehicle-dynamics-rlog/SKILL.md`](skills/vehicle-dynamics-rlog/SKILL.md) — ISO 8855 conventions, units, fidelity ladder, sign-convention sanity checks, variant-discipline rules.

## Harness friction (known)

Your sub-agent system prompt blocks `Write` on `(report|findings|summary|analysis).*\.md$`. Return the report content in your final text response; the orchestrator will persist it.

## What `REPORT.md` must contain

Stated platform; clamped-vs-predicted statement; consistent variant ladder with per-regime breakdown; marginal-drop column with named accounting scheme; honest regression flags. Plus paths to the three RPI phase artifacts under `rpi/runs/<ts>/`.
