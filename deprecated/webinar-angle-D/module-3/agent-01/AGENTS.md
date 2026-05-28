# AGENTS.md — webinar-angle-D / module-3 (skill v0.5, after self-improvement)

Substrate is the same single domain-authored skill folder as M2, **after** two rounds of the self-patching loop — the domain expert has shown the skill's failure modes to the agent, and the agent has patched the skill itself. A one-line **computational sensor** has been added that no future iteration can regress past.

## Project context

Sim-real correlation runtime around the CommonRoad **kinematic single-track (KS)** vehicle dynamics model. KS is integrated over real openpilot rlog driving data; the lateral state it predicts (yaw rate `ψ̇`, lateral acceleration `a_y`) is compared against measured truth channels from the same rlog.

- KS implementation: [`code/ks_model.py`](code/ks_model.py).
- Sim-CSV producers: [`code/generate_simdata.py`](code/generate_simdata.py) (Tesla), [`code/generate_simdata_ford.py`](code/generate_simdata_ford.py) (both Ford platforms). Already-produced CSVs live under `data/sim/segments/<PLATFORM>/<device>/<route>/<idx>/sim.csv`.
- Python 3 on PATH with `pandas`, `numpy`, `scipy`, `matplotlib`, `sklearn` already installed. Use `python3`, never `python`. No venv to source.
- Vehicle parameters: [`code/parameters.py`](code/parameters.py) — `PARAM_BY_PLATFORM[platform_str]`. Never hand-write.

## What's in this harness

```
skills/
  lateral-fidelity-triage/
    SKILL.md     ← v0.5 — patched after two rounds of self-improvement
    triage.py    ← helper module the skill imports
    sensor.py    ← one-line computational sensor, can be run on any candidate variant
```

That's it. No `references/`, no `evals/`, no separate domain-knowledge file. Everything is inside the skill.

## How to use it

Read `skills/lateral-fidelity-triage/SKILL.md` metadata first; load its body when relevant; run the procedure. Run `sensor.py` against your best variant before reporting it.
