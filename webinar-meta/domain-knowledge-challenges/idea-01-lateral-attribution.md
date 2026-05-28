---
title: Idea 01 — Lateral attribution
slug: idea-01-lateral-attribution
domain: vehicle-dynamics
tests:
  - attribution-discipline
  - regime-segmentation
  - operating-contract
  - metric-selection
  - truth-channel-discovery
best-fit-angles: [01-accretion, 04-author, 05-experiment]
weak-fit-angles: [02-empathy, 03-harness-as-product]
success-metrics:
  - id: truth-channel-correct
    type: binary
    rubric: the report scores against a measured channel, not a clamped or self-predicted one
    evidence-in-report: report names the scored channel and identifies it as measured, citing the dataset/source
  - id: contract-acknowledged
    type: binary
    rubric: the report states which channels are clamped to truth vs predicted by the model
    evidence-in-report: an explicit clamped-vs-predicted statement in the methodology section
  - id: regime-breakdown-present
    type: binary
    rubric: the report breaks out error by regime (straight / cornering / transient), not only an aggregate
    evidence-in-report: a per-regime table or chart of the chosen metric
  - id: methodology-consistent
    type: binary
    rubric: same segment list and same metric definition across every variant on the ladder
    evidence-in-report: variant table shares a fixed segment-set / regime-mask declaration in its header or caption
  - id: attribution-coherent
    type: numeric
    rubric: "|Σ marginal RMSE drops − total drop| / total drop (no double-counting)"
    threshold: "< 0.15"
    evidence-in-report: marginal-RMSE column and total-drop value both present and reconcilable
  - id: honest-regression-flagged
    type: binary
    rubric: any variant that worsened the metric is reported as a regression with a physical reason; vacuous if no regression occurred
    evidence-in-report: variant table includes regression rows with a physical-cause column, OR an explicit "no regressions observed" statement
naked-prompt-audit:
  metric-named: false
  platform-named: false
  contract-named: false
  catalogue-suggested: false
  scoring-procedure-suggested: false
---

# Idea 01 — Lateral attribution

## The naked prompt

```
The lateral predictions from our vehicle model aren't as good as they should be.
Make them better, and tell me how much each change you made contributed to the
improvement.
```

Every agent of every module of every angle receives this prompt verbatim. Nothing else from this file leaks in. The substrate of each module is what compensates (or fails to compensate) for the absence of hints.

## Why this is challenging in general

The hard thing is not building a better model. It is **constituting the problem before solving it**. Five things are deliberately not given — and most agents (human or AI) without domain context will get at least three of them wrong without flagging any.

| # | Trap | What goes wrong | Substrate cure | Visible artefact in M1 report |
|---|---|---|---|---|
| 1 | **Metric selection** | RMSE? MAE? Peak? % time within tolerance? Each privileges a different upgrade and produces a different ladder. | Skill / AGENTS.md that pins the metric and its physical meaning. | A number quoted without saying what was measured or why. |
| 2 | **Truth-channel discovery** | Multiple data sources exist; some have measured-vs-predicted truth, others only have predictions. Defaulting to the familiar source produces confident-looking metrics that aren't measuring what they claim. | Truth-channel matrix per platform in AGENTS.md. | "Self-consistency" reported as accuracy, or a platform without truth selected without comment. |
| 3 | **Operating contract** | Parts of the model state are clamped to measured values, parts are predicted. "Fidelity on the clamped channel" is technically true and operationally meaningless. | One line in AGENTS.md naming what is clamped vs predicted. | Report praises a channel whose value is trivially right by clamping. |
| 4 | **Variant catalogue** | A weak agent proposes one big leap (KS → neural net) and reports aggregate improvement, losing attribution. A strong one proposes a fine-grained ladder. A *very* strong one recognises that some upgrades are illegitimate within the contract (e.g. unclamping). | Reference doc with bounded catalogue of legitimate upgrades. | Single-variant report, or a ladder mixing legitimate and contract-violating moves. |
| 5 | **Attribution discipline** | Marginal vs Shapley vs ablation — all valid, all producing different numbers. Running variants in series and crediting each with its own RMSE drop double-counts when two upgrades close overlapping residual. | Skill enforcing fixed order with strict marginal accounting in the report table. | Marginal drops sum to more than the total drop. |

These traps generalise. (1) is the bias-variance question in disguise. (2) shows up every time a data scientist runs a model against a dataset they didn't collect. (3) is the bug that takes down most production ML systems on the day a "trivial refactor" silently changes what the model is conditioning on. (4) is the vibe-shipping anti-pattern. (5) is the half-life of every aggregate metric reported in any ML paper.

The substrate's job is not to make the agent smarter; it's to make these failures **visible**.

## Why it works for the workshop angles

For **01 accretion** — every trap maps one-to-one onto a substrate layer (see table). The audience reads M1's report, names the traps it hit, then watches M2's AGENTS.md grow the line that cures one, M3's skill add the procedure, M4's eval verify it.

For **04 author** — the substrate the domain expert writes *is* the contract clarification, the truth-channel matrix, and the variant catalogue. The expert seat turns the under-specified question into a sharp one in front of the audience.

For **05 experiment** — tests whether workflow / universal-agent / bespoke tiers each handle attribution differently. A workflow hardcodes the ladder, an agent with a skill adapts it, a bespoke agent proposes a new rung.

Weaker fit for **02 empathy** (per-turn token cost isn't the centrepiece here) and **03 harness-as-product** (no six-component spine is naturally visible).

## Predicted M1 vs M4 spread

- **M1** — high risk of picking the wrong data source. Likely to default to the platform with more segments, miss the absence of a truth channel, and either silently fake a metric (self-consistency) or claim accuracy on a clamped channel. The report looks credible at a glance and is wrong in a way that requires domain knowledge to spot.
- **M2** — fixes the data-source and clamping questions via the truth-channel matrix and operating-contract section in AGENTS.md. Still trips on attribution discipline (variant ladder under-specified, no formal marginal accounting). Numbers are real; methodology is fuzzy.
- **M3** — ladder grounded in the catalogue. Attribution is honest. May report unflattering findings (a canonical upgrade making things worse) with a physical reason. This is the "skill makes the agent more honest, not more optimistic" beat.
- **M4** — most disciplined, eval-passing, defensible. The eval rejects reports that don't acknowledge the contract or latch onto the wrong channel.

The spread is *categorical*, not just *quantitative*: M1 is at risk of measuring the wrong thing entirely; M4 is the only report a senior engineer would sign off on.

## Iteration log

- **2026-05-26 — webinar-angle-A, iter 1.** Used an earlier, leakier variant of the prompt that named "speed-known mode" and "yaw rate." Hardened to the current naked version after retro (see `webinar-angle-A/_observations/`). The leakier prompt is retained here as the comparison case: even with the hint, M1 still tripped traps 2/3 in iter 1, which is what justified keeping the harder prompt as canonical rather than reverting.
