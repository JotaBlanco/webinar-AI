---
title: closing-the-loop
description: How the m4 inner loop is structured — the iterate skill, the CV-based dev/test discipline, RPI phase separation, parallel-rung subagents, and the stagnation-reset gate. Read this once early so you know what's automatic vs what you decide.
when-to-load: First thing on a fresh m4 session, before you start iterating. Re-read in any session that hits a `compact_and_restart` route from critique-residuals.
load-cost: ~800 words.
updated: 2026-06-02
---

# Closing the loop — m4's inner-loop discipline

m3.v2 made the agent reliable (skills). m3.v3 made it search structurally
(`models/` + `MODELS.md`). **m4's job is to close the loop**: make every
iteration auto-score, auto-log, and auto-route, so the agent does in 20
iterations what m3.v3 cohorts did in 3.

This doc explains how the five m4 mechanisms (iterate, CV+test discipline,
RPI, parallel-rung subagents, stagnation reset) compose.

---

## The iterate skill is the inner loop

Every model candidate goes through one tool call:

```python
from skills.iterate.iterate import iterate
result = iterate("models/<candidate-name>")
```

`iterate` runs the verifier gate (k-fold route-grouped CV, residual structure,
fit diagnostics, gap-to-parent, gap-to-V1), writes the result to `TREE.json`,
appends to `MODELS.md` and `EXPERIMENTS.md`, and calls `critique-residuals`
to emit a routing string. Each call is one node in the search tree.

**Do not manually score candidates.** Every score that doesn't pass through
`iterate` is a silent un-logged node; the cohort failure mode is silently-
re-converging on the same approach because half the attempts weren't logged.
The skill is the discipline.

If you need a raw score without the registry side-effects (e.g. quick sanity
check on a half-built `predict.py`), call `score-model` directly. But the
moment you have a candidate you'd consider promoting, run `iterate` on it.

---

## CV and the dev/test split — what the agent sees

The dev split is what `iterate` scores against. The dev split is split by
**5-fold route-grouped CV**: every call returns pooled yaw RMSE and CTE RMSE
as `mean ± std`. The σ is what determines whether an improvement is signal
or noise.

**The test split is denied to the agent's optimization loop.** The
`score-model` skill refuses to score on `data/sim-only/test/` unless invoked
with `final=True`, and that's only allowed from `pre-flight-final-model
--final` — i.e. once, at the end. The dev/test gap is reported in the final
preflight; if dev ≫ test by more than the cohort's σ band, the gate warns.

Why both: the dev CV gives noise-aware iteration; the frozen test catches the
overfitting failure mode that grows with the number of iterations (CMU 2026:
"as sample count grows, the verification gap widens"). With m4's iterate
loop you'll be running 2-3× more iterations than m3.v3 — the test split is
insurance against the cost of that.

Route-grouped specifically because the agent-07 cohort finding (§6 of
`m4-cohort-findings.md`) showed naive splits overfit asymmetric-bias levers
that the full-dataset fit had no problem with.

### What the CV σ actually measures (precise division of labour)

The σ from `score_cv` is **route-evaluation variance** — how stable the
pooled RMSE is across 5 route-grouped subsets of the dev split. The
candidate's fit was done globally upstream (you fit on the whole dev set
before calling iterate); the CV here doesn't re-fit on each fold. So the
σ tells you:

- ✅ "Is one outlier route dominating my pooled metric?" (a real failure mode)
- ✅ "Is this +0.3% improvement vs parent real, or noise in which routes
  averaged out?" (the signal-above-noise gate)
- ❌ **Not** "does this fit generalize?" — that's a train/dev question, and
  the agent already did the fit globally.

The overfitting story from cohort §6 (agent-07's asymmetric-bias subset fit
flipped Lightning's sign) is a **fitting** failure — the agent fit on a
non-representative subset. The gate that catches *that* is the **dev/test
gap at preflight `--final`**, not the iterate-level σ bars. The two
mechanisms divide the labour:

| Mechanism | Catches |
|---|---|
| `score_cv` σ in iterate gate | "this improvement is within route-pooling noise" |
| dev/test gap in `pre-flight --final` | "I overfit the dev split across N iterations" |

If you're seeing `signal-below-noise` warnings, that's the σ catching
route-sensitivity, not overfit. Read it as "my route sample is small;
this delta is in the noise" rather than "this model will fail on test."

### How noisy is the σ itself?

The σ is computed from 5 fold-pooled RMSEs with `ddof=1`. Five numbers is
enough to flag big variance but the std-of-5 itself has a wide
confidence band. **A real-but-small improvement may bounce in and out of
`signal-above-noise` purely by which routes landed in which folds.** The
gate is honest about this — it doesn't mean the improvement isn't real.

The right way to read it:
- **One `signal-below-noise` warn** is not damning. Try the candidate
  another way (different parent, slight reformulation) and see if the
  pattern repeats across MODELS.md entries.
- **Three consecutive `signal-below-noise` warns on the same branch**
  IS the stagnation signal — it's what `iterate` watches for and what
  triggers the `compact_and_restart` route.

Raising k to 10 doesn't help much (we have limited routes; folds shrink
and the per-fold RMSE itself gets noisier). The right answer is reading
patterns across iterates, not over-reacting to a single flag.

---

## RPI — when to phase-separate

For tasks where the rung-1 attempt is real, run the three RPI phases
(`bash rpi/run-research.sh`, then `run-plan.sh`, then `run-implement.sh`).
The phase separation moves the rung-1 decision out of a context-fill-saturated
session and into a fresh-context Plan phase. See `rpi/README.md` for the
mechanics.

For tasks where you already know what you want to build, RPI is overhead. The
RPI hard-lock is opt-in — the iterate skill works the same way with or
without it.

**The stagnation reset is RPI-on-demand.** If `iterate` returns
`stagnation: True` (3 consecutive warn/fail nodes on the same branch), the
recommended next move is to start a fresh Claude Code session with only
`EXPERIMENTS.md`, `TREE.json`, and the current leader's `predict.py` in
context. You don't need to invoke `rpi/run-*.sh` — just open a fresh session
and seed it minimally.

---

## Parallel-rung subagents — when to fan out

If your wall clock allows running multiple sessions in parallel, the
`launch-rungs/` machinery fans out 4 subagents (rung-0 polish, rung-0
orthogonal residual learner, rung-1 dynamic ST, rung-1 regime-switched). Each
runs the same loop in its own context window; the orchestrator picks the
dev-CV winner.

This is **context isolation, not role-play**. Every subagent uses the same
skills and references; only the structural starting rung differs. The pattern
is the AlphaEvolve / AIDE / Anthropic-multi-agent-research consensus —
structured divergence with a real verifier as the picker. It is *not* the
"yaw specialist + CTE specialist" pattern, which the 2026 literature
(Cognition, Wasowski) has hardened against and m3.v2 already ruled out.

---

## The five mechanisms in one picture

```
  Orchestrator session
      │
      ├─ (optional) rpi/run-research.sh → RESEARCH.md (locked)
      ├─ (optional) rpi/run-plan.sh     → PLAN.md (locked)
      ├─ (optional) launch-rungs/launch.sh — fans out N subagents in parallel
      │
      └─ Implementation:
            ┌────────────────────────────┐
            │  for candidate in plan:    │
            │    build models/<name>/    │
            │    iterate(models/<name>)  │ ← verifier gate, TREE.json, MODELS.md
            │      └─ critique-residuals │ ← typed-grounded routing
            │      └─ if stagnation:     │
            │         compact + reset    │ ← fresh context
            │  pick dev-CV leader        │
            │  preflight --final         │ ← test split reads here only
            │  ship                      │
            └────────────────────────────┘
```

All five mechanisms compose. The minimum is: build a candidate, run
`iterate` on it, follow the routing. Everything else is opt-in scaffolding
for when the task needs it.
