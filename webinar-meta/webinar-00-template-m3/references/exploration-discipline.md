---
name: exploration-discipline
description: How to keep yourself from locking in on the first approach. A short protocol for naming alternatives before committing, and a log template for tracking what you've already tried.
when-to-load: At the start of the task, and again any time you find yourself iterating on the same approach without progress for more than ~15 minutes.
load-cost: ~400 words.
---

# Exploration discipline

Modelling tasks reward divergence then convergence. The trap is silent re-convergence on the same approach, dressed in new variable names. Two cheap practices keep that from happening.

## Before you commit to an approach — name three

When you've finished diagnosis and are about to start fitting, write down **at least three genuinely different approaches** that might close the residual you're seeing. One line each, with a one-line argument *for* it:

> 1. Polynomial steering scale on Mach-E — residual concentrates in high-curvature segments; nonlinear g may absorb it.
> 2. Per-segment δ₀ from straight-driving rows — per-segment yaw-bias spread is wide; offset is segment-specific.
> 3. First-order yaw lag with longer τ — high-frequency oscillations in transient regime suggest the lag is under-fitted.

"Genuinely different" is the key word. Three flavours of polynomial g do not count. The point is to force a *choice* — and to make the not-chosen options visible so they can be tried later.

Then pick one, try it, score it, log it (see below). If the chosen approach doesn't beat dev by a meaningful margin (~2% on at least one KPI), come back to the list and try the next.

This is a divergence-prompting protocol, not a multi-agent dance. You stay one thread. The discipline is that the alternatives get *named on paper* before commitment, not muttered as "I considered…" in the report.

## EXPERIMENTS.md — keep a visible log of approaches tried

Maintain a single file at the root of your working directory called `EXPERIMENTS.md`. Append-only. One entry per concrete attempt:

```
## E03 — Per-segment δ₀ on Mach-E (gated by a_lat < 0.3)
- Hypothesis: per-segment bias spread is wide; offset is segment-specific.
- What I changed vs E02: replaced platform-wide δ₀ with median(delta_road) on straight rows.
- Result (dev): yaw 0.00882 → 0.00821 (+6.9%); CTE 134.2 → 88.7 (+33.9%).
- Verdict: keep. Combine with E04 (polynomial g) next.
- Things this rules out: bias was not noise — correction landed.
```

Why this matters: by experiment 6 or 7 you will be tempted to "try per-segment δ₀ again with slightly different gating", not realising it's a variant of E03. The log makes the duplication visible *to yourself*. It also gives the orchestrator a clean trail of what was tried and why, which is far more useful than a final-state REPORT.md alone.

A starter template lives at the template root as `EXPERIMENTS.md` — copy or extend it.

## When to stop

You're done exploring when the **named alternatives are exhausted** OR when your latest attempt produced no dev-KPI movement in either direction. If neither is true, you have at least one option left worth trying — go try it.

You should improve on this if you can.
