# AGENTS.md — webinar-angle-D / module-2 (skill v0.1, first crystallisation)

This module's substrate is **a single domain-authored skill folder** — the result of a senior engineer (the "domain expert") sitting down and crystallising their first pass at a fit-and-validate skill from a real working session. The agent's job is to do the task using that skill.

## Project context

Sim-real correlation runtime around the CommonRoad **kinematic single-track (KS)** vehicle dynamics model. KS is integrated over real openpilot rlog driving data; the lateral state it predicts (yaw rate `ψ̇`, lateral acceleration `a_y`) is compared against measured truth channels from the same rlog.

- KS implementation: [`code/ks_model.py`](code/ks_model.py) — function `simulate_ks(...)`.
- Sim-CSV producers: [`code/generate_simdata.py`](code/generate_simdata.py) (Tesla), [`code/generate_simdata_ford.py`](code/generate_simdata_ford.py) (both Ford platforms). Already-produced CSVs live under `data/sim/segments/<PLATFORM>/<device>/<route>/<idx>/sim.csv`.
- Python 3 on PATH with `pandas`, `numpy`, `scipy`, `matplotlib`, `sklearn` already installed. Use `python3`, never `python`. No venv to source.
- Vehicle parameters: [`code/parameters.py`](code/parameters.py) — `PARAM_BY_PLATFORM[platform_str]`. Never hand-write.

## What's in this harness

```
skills/
  lateral-fidelity-triage/
    SKILL.md     ← v0.1 — first crystallisation by the domain expert
    triage.py    ← helper module the skill imports
```

That's it. No `references/`, no `evals/`, no separate domain-knowledge file. The skill is the whole substrate.

## How to use it

Read `skills/lateral-fidelity-triage/SKILL.md` metadata first; load its body when relevant; run the procedure. The skill imports `triage.py` from the same directory.

## Reporting

Final deliverable: `REPORT.md` at the module root with whatever the skill's reporting rule prescribes.
