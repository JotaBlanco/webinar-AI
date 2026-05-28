# AGENTS.md — webinar-angle-E / module-3 (universal agent + skill tier)

This module is the **universal-agent-plus-skill** rung of the four-scaffold comparison. The hand-built workflow from M2 is gone; in its place sits a `skills/` folder. You are a generalist agent; you read the skill metadata, decide which body to load, and execute the procedure with full latitude.

## Why this is a skill, not a workflow

The same 5-step logic that lived as five Python wrappers in M2 now lives as one `SKILL.md` plus its helper module. The agent loads metadata first (NC-12 — progressive disclosure: ~50 tokens), reads the body when relevant, and runs the procedure. A second skill is pre-staged in the same folder; compose if the task warrants it.

## Project context

Sim-real correlation runtime around the CommonRoad **kinematic single-track (KS)** vehicle dynamics model. The lateral residual under test is `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` (pre-computed in each Ford `sim.csv`).

- KS implementation: `code/ks_model.py`.
- Sim CSV producers: `code/generate_simdata_ford.py`. Output at `data/sim/segments/<PLATFORM>/<device>/<route>/<idx>/sim.csv`.
- Vehicle parameters: `code/parameters.py::PARAM_BY_PLATFORM[platform_str]`.
- Python 3 on PATH with `pandas`, `numpy`, `scipy`, `matplotlib`, `sklearn` installed. Use `python3`, never `python`. No venv.

## Operating contract

KS runs with `clamp_v_to_measured=True` and `clamp_delta_to_measured=True`. Speed and steering are inputs; the lateral residual is the only metric.

## What's in the harness

```
skills/
  yaw-divergence-triage/    ← primary skill — variant ladder
    SKILL.md
    triage.py
  regime-comparison/        ← sibling skill — per-regime diff/contrast
    SKILL.md
    compare.py
```

No `tools/` (deleted from M2 — the workflow logic moved into the skill). No `references/`, no `evals/`.

## Reporting

Final deliverable: `REPORT.md` at the module root. Each skill prescribes the reporting shape for its own outputs.
