---
name: exploration-discipline
description: How to keep yourself from locking in on the first approach. A short protocol for naming alternatives before committing, the EXPERIMENTS.md schema (including the required `Rung:` tag), and the rule that the shipped model must differ structurally from V1.
when-to-load: At the start of the task, and again any time you find yourself iterating on the same approach without progress for more than ~15 minutes.
load-cost: ~500 words.
---

# Exploration discipline

Modelling tasks reward divergence then convergence. The trap past cohorts have fallen into isn't a lack of divergence — it's **convergence to the same rung-0 local optimum, by every agent, every time.** In m3.v2, six of ten agents shipped the same coefficients to three decimal places. That's not search; that's transcription.

m3.v3 raises the floor: rung-0 kinematic-single-track + `δ₀` + lag is pre-shipped as V1 (`code/v1_baseline.py`), scored, and treated as the new baseline. Re-fitting V1's coefficients buys ~0 points. To improve on V1 you need a different *shape* of model, and the discipline here is how to find one.

This template enforces:
1. **Name alternatives across model structures before committing**, so the structure-space gets a fair search.
2. **The shipped model must differ structurally from V1** — not just in fitted coefficients. Preflight checks this. The cohort needs evidence about what shapes beat V1; that evidence only arrives if agents ship beyond V1.

## Before you commit to an approach — name five, with at least three different model structures

When you've finished diagnosis and are about to start fitting, write down **at least five genuinely different approaches** that might close the residual you're seeing. One line each, with a one-line argument *for* it.

**Hard rule: at least three of the five must be different *model structures*, not five flavours of V1's shape.** "Polynomial g on Mach-E", "polynomial g on Lightning", and "polynomial g with bounds" are *one* approach in three costumes — they all stay inside V1's kinematic-single-track form and a refit of V1 with these alone scores ~V1. A different *structure* is something V1 cannot reach by re-fitting coefficients: a dynamic single-track ODE, a nonlinear tyre, a residual-learning layer on top of V1, a sensor-fusion / complementary-filter approach, a regime-switched model.

Example list that satisfies the rule (the structures, not specific recipes):

> 1. *(structure)* Linear dynamic single-track with slip angles — transient regime carries the largest residual against V1; V1's first-order lag is a band-aid for the missing transient.
> 2. *(structure)* Regime-switched model — V1 on straight-driving, something else on transient. Pick the switch threshold from residual diagnostics.
> 3. *(structure)* Residual learner on top of V1 — fit a small model on V1's residual against allowlist features; ship V1 + learned residual.
> 4. *(structure)* Complementary filter / sensor fusion — blend V1 with a steering-derivative-driven model in frequency domain.
> 5. *(orthogonal)* Multi-seed fold averaging on V1 — current dev-score swings with seed, suggesting noise that averaging would cancel.

"Genuinely different" is the key word. **Three flavours of polynomial g do not count as three approaches** — they're one approach in three costumes, all inside V1's shape. The point is to force a *choice across the strategy space* and to make the not-chosen options visible so they can be tried later.

Then pick one, build it under `models/<name>/`, assess it (compare against V1, not V0), log it. If the chosen approach doesn't meaningfully beat V1 on dev (~1% on at least one KPI), come back to the list and try the next.

## The shipped model must differ structurally from V1

`pre-flighting-final-model` checks that the shipped `final-model/predict.py` is *not* a thin wrapper around `code.v1_baseline.predict_v1` (i.e. it isn't "import V1 and re-fit coefficients"). It also checks `MODELS.md` contains at least three candidate models, each in `models/<name>/`, with at least one structurally distinct from V1.

The shipped model does not need to *beat* V1 — what's required is a structural change attempt. If three structurally-different models all lost to V1, ship V1 and document the negative result. That is itself a cohort contribution.

## EXPERIMENTS.md schema — `Rung:` is required

Maintain a single file at the root of your working directory called `EXPERIMENTS.md`. Append-only. One entry per concrete attempt:

```
## E03 — Per-segment δ₀ on Mach-E (gated by |yaw_rate_pred_rads| < 0.03)
- Rung: 0
- Hypothesis: per-segment bias spread is wide; offset is segment-specific.
- What I changed vs E02: replaced platform-wide δ₀ with median(delta_road) on straight rows.
- Result (dev): yaw 0.00882 → 0.00821 (+6.9%); CTE 134.2 → 88.7 (+33.9%).
- Verdict: keep. Combine with E04 (polynomial g) next.
- Things this rules out: bias was not noise — correction landed.
```

The `Rung:` field is required on every entry. Permitted values: `0`, `1`, `2`, `3`, `orthogonal`. The preflight check counts entries tagged `1+` or `orthogonal`. Tagging `Rung: 0` on a rung-1 attempt to slip past the check is dishonest — and detectable next cohort when we audit the actual model code in the log entries.

Why this matters: by experiment 6 or 7 you will be tempted to "try per-segment δ₀ again with slightly different gating", not realising it's a variant of E03. The log makes the duplication visible *to yourself* (every entry is `Rung: 0`). It also gives the orchestrator a clean trail of what was tried and why, which is far more useful than a final-state REPORT.md alone.

A starter template lives at the template root as `EXPERIMENTS.md` — copy or extend it.

## When to stop

You're done exploring when **at least three structurally-different candidate models live under `models/`**, each with an `assessment.md`, and `MODELS.md` is up to date. If your best candidate beats V1, ship it. If not, ship V1 and write up which structures lost and why in `REPORT.md` — that is a useful result.

You should improve on this if you can.
