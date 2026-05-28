# AGENTS.md — webinar-angle-D / module-4 (two composable skills on one harness)

Substrate is the mature `lateral-fidelity-triage` skill from M3, **plus** a second composable skill — `regime-segmentation` — authored off-stage by the same domain expert via the same crystallise → self-patch loop. Both live in the same `skills/` folder; the universal agent loads metadata for each, then bodies on demand.

## Project context

Sim-real correlation runtime around the CommonRoad **kinematic single-track (KS)** vehicle dynamics model. KS is integrated over real openpilot rlog driving data; the lateral state it predicts (yaw rate `ψ̇`, lateral acceleration `a_y`) is compared against measured truth channels from the same rlog.

- KS implementation: [`code/ks_model.py`](code/ks_model.py).
- Sim-CSV producers: [`code/generate_simdata.py`](code/generate_simdata.py) (Tesla), [`code/generate_simdata_ford.py`](code/generate_simdata_ford.py). CSVs at `data/sim/segments/<PLATFORM>/<device>/<route>/<idx>/sim.csv`.
- Python 3 on PATH with `pandas`, `numpy`, `scipy`, `matplotlib`, `sklearn` installed. Use `python3`, never `python`. No venv to source.
- Vehicle parameters: [`code/parameters.py`](code/parameters.py).

## What's in this harness

```
skills/
  lateral-fidelity-triage/      ← skill #1, v0.5
    SKILL.md
    triage.py
    sensor.py
  regime-segmentation/          ← skill #2, v0.3 — authored off-stage following the same loop
    SKILL.md
    segment.py
```

No `references/`, no `evals/`. The skills are the whole substrate.

## How to use it

Read each skill's metadata first; load bodies on demand. The two skills are designed to **compose** — segment a CSV first with `regime-segmentation`, then run the variant ladder with `lateral-fidelity-triage` over the regime-tagged DataFrame. The second skill exposes a `segment.tag(df)` helper that the first skill can consume.

Decide composition order yourself based on what each skill's `when-to-load` says.
