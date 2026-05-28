# AGENTS.md — webinar-angle-E / module-4 (universal agent + skill + RPI tier)

This module is the **RPI-loop** rung of the four-scaffold comparison. Same skills folder as M3; the difference is in *how you execute the task*. The agent simulates Horthy's Research → Plan → Implement three-phase loop within a single run by gating each phase on a separate artifact.

## Why this is the RPI rung

In a "real" RPI run, each phase would be a fresh context window reading only the previous artifact. Subagents don't fork that way, so this run **simulates RPI** — you write each phase's artifact before starting the next, and within each phase you actively *forget* and *re-derive* from the artifacts on disk rather than from your conversation memory. This protects the smart-zone of each phase from the working-context noise of the others (NC-28).

## Project context

Sim-real correlation runtime around the CommonRoad **kinematic single-track (KS)** vehicle dynamics model. The lateral residual under test is `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads` (pre-computed in each Ford `sim.csv`).

- KS implementation: `code/ks_model.py`.
- Sim CSV producers: `code/generate_simdata_ford.py`. CSVs at `data/sim/segments/<PLATFORM>/<device>/<route>/<idx>/sim.csv`.
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
  regime-comparison/        ← sibling skill — per-regime contrast
    SKILL.md
    compare.py
```

Same skills as M3. **Different execution protocol**.

## RPI protocol — mandatory, in order

You will produce **three artifacts**, in this order, each as a separate phase. Within each phase, do not skip ahead.

### Phase 1 — Research (writes `out/research.md`)

Read the data only. Do not commit to a variant ladder yet. Output a markdown file that contains:

- Which platforms are available and which have measured truth.
- Sample sizes per platform/segment.
- Coarse residual statistics (RMSE overall, per-regime) on the baseline column as-is, no preprocessing.
- Any anomalies you spot in the data (sign issues, gaps, NaN runs, outliers).
- Open questions you would want to resolve before picking a ladder.

Length: ~30 lines of markdown. Save to `out/research.md`. Do not load any skill body in this phase — read skill metadata only.

### Phase 2 — Plan (writes `out/plan.md`)

Pretend you are a fresh context that has only `out/research.md` and the skill metadata. Read both. Output a markdown plan that contains:

- Chosen platform (and why).
- The full variant ladder you will run, V0 → V_last, with one line per variant.
- The attribution scheme.
- The reporting shape (what `REPORT.md` will look like — section headers).
- A list of "explicitly out of scope" choices (variants you considered and rejected, e.g., V4 residual learner, with reason).

Length: ~25 lines. Save to `out/plan.md`. Lock it. Do not deviate in Phase 3.

### Phase 3 — Implement (writes `REPORT.md` at module root)

Pretend you are a fresh context that has only `out/plan.md` and the skill bodies. Load the skill bodies now. Execute the plan exactly. Write the final report to `REPORT.md` at the module root, populated with real numbers.

If you find a reason mid-Phase-3 that the plan was wrong, **do not silently change course**. Instead, finish the implementation against the locked plan, *then* note the dissent in a "Plan dissent" section at the bottom of `REPORT.md`.

## Reporting (final deliverable)

`REPORT.md` at the module root, written in Phase 3. Each skill prescribes the reporting shape for its outputs. Inside the report, mention which phase surfaced which decision (this is the workshop's evidence that the RPI split bought something M3 did not).
