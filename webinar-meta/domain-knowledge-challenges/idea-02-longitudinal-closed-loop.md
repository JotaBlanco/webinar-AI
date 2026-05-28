---
title: Idea 02 — Longitudinal closed-loop fidelity
slug: idea-02-longitudinal-closed-loop
domain: vehicle-dynamics
tests:
  - operating-contract
  - regime-segmentation
  - truth-channel-discovery
  - data-provenance
  - tradeoff-framing
  - failure-repro
best-fit-angles: [01-accretion, 04-author, 05-experiment]
weak-fit-angles: [02-empathy, 03-harness-as-product]
success-metrics:
  - id: new-contract-stated
    type: binary
    rubric: report explicitly states, for the new model, which channels are predicted vs clamped (or "nothing clamped")
    evidence-in-report: methodology section names the predicted state and any remaining clamped inputs
  - id: closed-loop-evaluated
    type: binary
    rubric: validation integrates the model forward in time from initial conditions, not one-step open-loop prediction; report states which mode
    evidence-in-report: methodology names "closed-loop" or "integrated forward from t0" and a horizon
  - id: integration-horizon-justified
    type: binary
    rubric: integration / reset horizon is named AND tied to a downstream use case rather than chosen for flattery
    evidence-in-report: a sentence linking horizon to use case (e.g., stopping-distance use case requires a full braking-event horizon)
  - id: input-causality-clean
    type: binary
    rubric: no inputs used that are downstream of the predicted quantity (e.g., wheel-speed sensors used to "predict" longitudinal acceleration)
    evidence-in-report: input list is explicit; borderline channels (wheel speed, sensed torque) called out with a causality note
  - id: combined-slip-acknowledged
    type: binary
    rubric: combined-slip / cornering regime is evaluated separately, or its exclusion is explicitly justified by use case
    evidence-in-report: per-regime table includes a combined-load row, OR a methodology line excluding it with a reason
  - id: regime-breakdown-present
    type: binary
    rubric: per-regime error reported (cruise / accel / brake / coast / combined-load), not only aggregate
    evidence-in-report: per-regime table or chart of the chosen metric
  - id: honest-degradation-flagged
    type: binary
    rubric: any regime where the new model is worse than the baseline (lateral-clamped) reported as such with a physical reason; vacuous if no degradation occurred
    evidence-in-report: per-regime table includes a "vs baseline" column with regressions called out and reasons, OR an explicit "no regressions" statement
  - id: attribution-coherent
    type: numeric
    rubric: "|Σ marginal RMSE drops − total drop| / total drop (no double-counting), if a variant ladder is used"
    threshold: "< 0.15"
    evidence-in-report: marginal-RMSE column and total-drop value both present and reconcilable; vacuous if no ladder was built
naked-prompt-audit:
  metric-named: false
  platform-named: false
  contract-named: partial   # deliberate — the brief names that measured longitudinal speed is currently an input and must stop being one. It does NOT name other clamps, the full predicted-vs-clamped split, the integration horizon, or the regime structure. See note in "Why this is challenging" below.
  catalogue-suggested: false
  scoring-procedure-suggested: false
---

# Idea 02 — Longitudinal closed-loop fidelity

## The naked prompt

```
Our vehicle model currently takes measured longitudinal speed as an input —
that's the crutch we need to remove. Build a longitudinal model that predicts
that channel itself, accurately enough to stand on its own.
```

Every agent of every module of every angle receives this prompt verbatim. Nothing else from this file leaks in. The substrate of each module is what compensates (or fails to compensate) for the absence of hints.

**Note on naked-prompt discipline.** This brief deliberately names one element of the current operating contract — that measured longitudinal speed is an input today and must stop being one. That is the *request*, not scaffolding: any real engineer briefing a colleague would say this much, and stripping it to "make it more accurate" stops being naked-prompt discipline and starts being trap-promotion. What stays out of the prompt are the things substrate is supposed to supply: which other channels are clamped, which inputs are legitimate vs downstream, what the integration horizon should be, what regimes to break out, what metric to score on. The `contract-named: partial` field in the audit records this trade.

## Why this is challenging in general

[[idea-01-lateral-attribution]] was about *attribution* within a fixed contract: the model already runs, the lateral channel is the scored target, the question is which upgrade earned which slice of the improvement. Idea-02 changes the contract itself. The current model is only as good as it is because it takes measured longitudinal speed as an input — that clamp silently suppresses state drift across the whole simulation. The task is to remove the crutch and rebuild, without the crutch reappearing in a less visible form.

The brief tells the agent the named crutch exists. What it doesn't tell them is everything that has to come with removing it. Six things are deliberately not given. A weak agent will get four of them wrong without flagging any.

| # | Trap | What goes wrong | Substrate cure | Visible artefact in M1 report |
|---|---|---|---|---|
| 1 | **Soft re-clamping** | Agent removes the named measured-`vx` input and then plumbs in a wheel-speed sensor, ABS-derived signal, or sensed engine-torque estimate — all of which are downstream of the very `vx` being "predicted." The contract change is cosmetic; the model is still being told its own answer by a different name. | AGENTS.md listing legitimate (commanded / upstream) vs illegitimate (sensed / downstream) inputs, with a causality rule. | New input list undeclared, or includes wheel speed / sensed torque without a causality note. |
| 2 | **Open-loop validation** | Agent removes the clamp but still validates timestep-by-timestep against measured state. Errors look tiny because each prediction restarts from truth. The closed-loop drift — the *only* reason removing the clamp matters — is invisible. | Skill enforcing closed-loop integration from initial conditions over a stated horizon. | RMSE quoted without a horizon, or a horizon of "one timestep." |
| 3 | **Combined-slip blindness** | Agent treats longitudinal as separable from lateral. Combined-slip tire physics says they aren't — longitudinal grip falls as lateral utilisation rises. Model is excellent in straight-line cruise and useless in any cornering or trail-braking event. | Reference doc on combined slip; eval requiring a cornering / combined-load regime row. | Single aggregate metric; no cornering / combined-load row. |
| 4 | **Regime asymmetry within longitudinal** | Cruise, accelerating, braking, coasting, and hill-grade are all longitudinal but driven by different physics (drivetrain torque, brake torque, aero drag, grade, regenerative braking). An aggregate metric averages over a regime mix that has nothing to do with deployment use; one regime can collapse without moving the headline number. | Skill enforcing per-regime breakdown across longitudinal regimes, plus a manifest of regimes present in the validation set. | Per-regime table missing, or regimes pooled into a single "longitudinal" bucket. |
| 5 | **Horizon flattery** | Integration horizon silently chosen so drift hasn't accumulated — short enough to flatter, or reset frequently enough to mask the closed-loop divergence the change was meant to expose. | Skill pinning horizon(s) to downstream use cases (full braking event, full lap, full drive cycle). | Horizon unspecified, or visibly chosen post-hoc. |
| 6 | **Quantity confusion** | Agent reports RMSE on `ax` when the consumer needs `vx`; or on `vx` when the consumer needs stopping distance. Each integral amplifies error differently; the quantity reported determines whether the model "passes." | Reference linking predicted quantity to consumer use case. | Metric named on a quantity the consumer doesn't use. |

These traps generalise beyond vehicle dynamics. (1) is the leakage / time-travel bug in every ML pipeline, dressed as a contract migration. (2) is the open-loop / closed-loop split in any sequential model (LLM eval, control, simulation). (3) is cross-axis coupling that bites every modular system whose modules secretly share state. (4) is regime-mix bias — the eval set's regime distribution silently determines the headline metric. (5) is eval-set selection bias that makes ML papers irreproducible. (6) is the bias-variance question, again, in different clothes.

The substrate's job is not to make the agent smarter; it's to make these failures **visible** — especially the failure that the brief was followed to the letter (the named input is gone) while the crutch came back in through the next sensor over.

## Why it works for the workshop angles

For **01 accretion** — every trap maps one-to-one onto a substrate layer (see table). The audience reads M1's report, names the traps it hit, then watches M2's AGENTS.md introduce the contract / legitimate-inputs sections, M3's skill enforce closed-loop integration with a pinned horizon and per-regime breakdown, M4's eval reject reports that don't acknowledge the contract change or that omit the combined-load row.

For **04 author** — the domain expert's job *is* to surface the hidden lateral clamp and the combined-slip coupling in front of the audience. The naked prompt looks reasonable to a non-expert ("just make it more accurate"); the expert seat is what turns it into a sharp problem.

For **05 experiment** — tests how each tier handles the open-loop → closed-loop shift. A workflow with the integration baked in will quietly drift; a universal agent with a skill will rediscover the horizon question each run; a bespoke agent should propose its own horizon and defend it against the use case.

Weaker fit for **02 empathy** (per-turn token cost isn't the centrepiece) and **03 harness-as-product** (the six-component spine isn't naturally visible — though the closed-loop integration loop is arguably itself a harness, this isn't where the angle shines).

## Predicted M1 vs M4 spread

- **M1** — high risk of the soft re-clamping failure. Removes measured `vx` from the input list as briefed, then wires in wheel speed (or sensed torque) and calls it a prediction. Validates open-loop because that's how the legacy was validated. Reports numbers that look like the brief was followed; the crutch is still there, just renamed.
- **M2** — fixes the input-causality trap via AGENTS.md (legitimate vs downstream inputs). Wheel speed is out, commanded torque is in. Still validates open-loop or with an unjustified horizon; combined-slip and longitudinal-regime asymmetry hidden inside an aggregate.
- **M3** — closed-loop integration with a pinned horizon. Per-regime breakdown across both longitudinal regimes (cruise / accel / brake / coast / grade) and a combined-load row. Likely reports an honest degradation in combined load relative to the clamped baseline — and is right to do so, because that regime is where the clamp was doing the most work. This is the "skill makes the agent more honest, not more optimistic" beat again.
- **M4** — most defensible. The eval rejects reports that quote a metric without a horizon, omit the combined-load row, pool longitudinal regimes, or use a sensed downstream signal as an input without a causality note.

The spread is *categorical*, not just *quantitative*: M1 is at risk of reporting a number for a contract change that didn't actually happen; M4 is the only report that survives the question *"what happens to this model the first time someone trail-brakes through a corner?"*

## Iteration log

- **2026-05-27 — draft.** Initial idea written. Not yet run against any angle.
