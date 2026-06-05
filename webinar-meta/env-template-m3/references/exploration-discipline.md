---
name: exploration-discipline
description: How to keep yourself from locking in on the first approach. A short protocol for naming alternatives before committing, the EXPERIMENTS.md schema (including the required `Rung:` tag), and the rule that you must log at least one rung-1+ climb attempt.
when-to-load: At the start of the task, and again any time you find yourself iterating on the same approach without progress for more than ~15 minutes.
load-cost: ~500 words.
---

# Exploration discipline

Modelling tasks reward divergence then convergence. The trap past cohorts have fallen into isn't a lack of divergence — it's **convergence to the same rung-0 local optimum, by every agent, every time.** Reading the m3 reports shows agents *considered* climbing and rejected it, because rung 0 is reliable and rung 1 looks expensive. The result is the cohort piles up around +48–57% over V0 and we still don't know whether rung 1 helps on this data.

The discipline in this template addresses both halves of that:
1. **Name alternatives across rungs before committing**, so the structure-space gets a fair search.
2. **Log at least one rung-1+ (or orthogonal) climb attempt** before declaring done — enforced by `pre-flighting-final-model`. The cohort needs evidence about whether rung 1 pays on this data; that evidence only arrives if agents try.

## Before you commit to an approach — name five, with at least three different model structures

When you've finished diagnosis and are about to start fitting, write down **at least five genuinely different approaches** that might close the residual you're seeing. One line each, with a one-line argument *for* it.

**Hard rule: at least three of the five must be different *model structures*, not five flavours of the same model.** "Polynomial g on Mach-E", "polynomial g on Lightning", and "polynomial g with bounds" are *one* approach in three costumes — they all stay on rung 0 of the structure ladder (see `approach-menu.md`). Climbing to rung 1 (dynamic single-track) or rung 2 (nonlinear tyre) is a *different structure*.

Example list that satisfies the rule:

> 1. *(rung 0, coefficient)* Polynomial steering scale on Mach-E — residual concentrates in high-curvature segments.
> 2. *(rung 0, coefficient)* Per-segment δ₀ from straight-driving rows — per-segment yaw-bias spread is wide.
> 3. *(rung 1, structure)* Linear dynamic single-track with slip angles — transient regime carries the largest residual; the first-order lag is a band-aid.
> 4. *(rung 2, structure)* Pacejka tyre on top of rung 1 — high-`a_lat` segments suggest tyre saturation; only worth it after rung 1.
> 5. *(orthogonal)* Multi-seed fold averaging — current dev-score swings with seed, suggesting noise in the fit.

"Genuinely different" is the key word. **Three flavours of polynomial g do not count as three approaches** — they're one approach in three costumes. The point is to force a *choice across the strategy space* — refine vs climb vs orthogonal — and to make the not-chosen options visible so they can be tried later.

Then pick one, try it, score it, log it (see below). If the chosen approach doesn't beat dev by a meaningful margin (~2% on at least one KPI), come back to the list and try the next.

## You must log at least one rung-1+ climb attempt

`pre-flighting-final-model` checks `EXPERIMENTS.md` and fails the bundle if no entry is tagged `Rung: 1` (or higher, or `orthogonal`). This isn't aspirational — it's mechanical. **Your shipped model can still be rung 0** if your climb attempt didn't beat it; what's required is that you *tried* and logged the result.

See `references/dynamics-formulations.md` § "Minimum viable rung-1 attempt" for a 30-line scaffold. The cost is lower than past cohorts assumed. If your climb fails or hurts, that is itself a contribution to the cohort — it lets the next agent skip the deadend (and the template `## Tried and shelved` section is where it goes).

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

You're done exploring when the **named alternatives are exhausted** AND your `EXPERIMENTS.md` includes at least one `Rung: 1+` or `Rung: orthogonal` entry. If neither is true, you have at least one option left worth trying — go try it.

You should improve on this if you can.
