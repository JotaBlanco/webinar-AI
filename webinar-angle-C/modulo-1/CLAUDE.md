---
title: KB003 — Sim-Real workshop runtime (data + code)
summary: Runtime sandbox for the sim-real correlation workshop. Holds the real driving data (data/raw/), the model outputs (data/sim/), and all the Python that turns the former into the latter. All research, design, and workshop write-ups live in [`../KB002/workshop-sim-real/`](../KB002/workshop-sim-real/).
updated: 2026-05-25
---

# KB003 — Sim-Real workshop runtime

This is the **data + code** half of the sim-real correlation workshop. It is the thing you run. The thing you *read* — workshop ideas, dream-team notes, simulation-tool comparisons, vehicle-specific model docs, agent-proposed agendas, public-dataset evaluations — lives in [`../KB002/workshop-sim-real/`](../KB002/workshop-sim-real/). If you are here to think, you are in the wrong place; go there.

Sister KBs:

- [`../KB001/`](../KB001/) — F1 project KB. F1-specific data sources and notes.
- [`../KB002/`](../KB002/) — Webinar curriculum KB. Includes `workshop-sim-real/` (this workshop's research home) and `public-data-sources/` (the 19-dataset evaluation that picked the data sitting in this KB).

## Layout

```
KB003/
  data/
    raw/segments/<PLATFORM>/<device>/<route>/<idx>/rlog.zst    ← downloaded by code/fetch_*.py
    sim/segments/<PLATFORM>/<device>/<route>/<idx>/sim.csv     ← produced by code/generate_simdata*.py
  code/                                                         ← all Python, flat (see code/_README.md)
  .venv/                                                        ← Python 3.13 virtualenv
```

Three platforms currently present under both `data/raw/segments/` and `data/sim/segments/`:

- `TESLA_MODEL_3` — 1.785 GB raw / 1025 segments. Tesla party DBC decode. Lateral KS prediction only; measured yaw-rate truth channel not yet decoded.
- `FORD_MUSTANG_MACH_E_MK1` — 0.817 GB raw / 315 segments. openpilot ford_lincoln_base_pt DBC. Both KS prediction *and* measured yaw-rate + lateral-G truth in the CSV.
- `FORD_F_150_LIGHTNING_MK1` — 0.597 GB raw / 230 segments. Same DBC. Same prediction-vs-truth structure.

## Operating contract

Real-data runs operate in **speed-known lateral-only** mode: measured `v` and measured `δ` are clamped at every integration step, so the KS model predicts only the lateral subset `(ψ, ψ̇, a_y, x, y)`. The longitudinal channel is input, not output. Full rationale in [`../KB002/workshop-sim-real/simulation-tools/commonroad/models.md`](../KB002/workshop-sim-real/simulation-tools/commonroad/models.md) under "Speed-known framing". Code-level summary in [`code/_README.md`](code/_README.md).

## How to run things

See [`code/_README.md`](code/_README.md). The three end-to-end demos:

```bash
source .venv/bin/activate
python code/run_ks_synthetic.py             # synthetic open-loop, no rlog needed
python code/generate_simdata.py             # Tesla rlog → KS → data/sim/
python code/generate_simdata_ford.py        # Mach-E + F-150 rlog → KS → data/sim/
```

## What is *not* here (and where it went)

This KB used to also hold workshop md content. As of 2026-05-25 all of that moved to KB002:

- workshop-idea, dream-team, agent-proposed agendas → `../KB002/workshop-sim-real/`
- simulation-tools comparison + commonroad deep-dive (philosophy, models, adapters, per-vehicle specs) → `../KB002/workshop-sim-real/simulation-tools/`
- public-dataset evaluation → `../KB002/public-data-sources/` (already lived there before the split)

If you came looking for any of those, follow the links.
