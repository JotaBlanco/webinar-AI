---
title: Idea 01 — Lateral fidelity attribution
summary: The vehicle dynamics model runs in speed-known mode. Improve its lateral prediction and quantify how much each addition contributes. Tests disciplined incremental engineering with attribution discipline; rewards the substrate that names the operating contract.
genre: numerical attribution
first-used: webinar-angle-A iter 1 (2026-05-26)
best-fit-angles: [01-accretion, 05-experiment]
---

# Idea 01 — Lateral fidelity attribution

## Why this is challenging in general

The hard thing is not building a better model. The hard thing is **attribution** — running a sequence of incremental changes such that each step's contribution is individually scored on the same data with the same metric, and the agent (or engineer) reports honest deltas instead of an aggregate "now it's better".

Five sub-traps are independently load-bearing, and almost any engineer (human or agent) without explicit discipline will trip at least one:

1. **Methodology drift across the ladder.** Each variant must be evaluated on the same segments, with the same regime masks, with the same metric definition. The natural failure mode is to subtly change the comparison (e.g. drop a hard segment "because it's noisy", or expand the regime mask "because the variant handles that case now") and report a number that is no longer comparable.

2. **Double-counting.** Two upgrades can independently close the same residual; if you run them in series and credit each with its own RMSE drop, the sum is greater than the variance closed. The honest attribution requires either a fixed order with strict marginal accounting or an ablation study.

3. **Confounding the metric with the contract.** Some part of the model's behaviour is *clamped to truth* (here: longitudinal). Reporting "the speed prediction is excellent" is technically true and operationally meaningless. An attribution is only honest if it acknowledges what the model is being given vs predicting.

4. **Regime imbalance hiding the signal.** Real driving data is mostly straight. An aggregate RMSE is dominated by the easy regime; an upgrade that closes the transient lie can look invisible at the aggregate level. The attribution must break out by regime or it's lying by averaging.

5. **The "swap the model" temptation.** When a residual is large, the instinct is to upgrade the model class wholesale (KS → ST → MB → neural). But each class change couples many physical changes at once, making attribution impossible. Discipline requires *one parameter, one change, one re-score*.

These traps generalise far beyond vehicle dynamics. They show up in any ML residual analysis, any A/B test ladder, any error budget decomposition, any "what's the marginal value of this feature" question. An agent that handles them well on a KS-vs-ST problem will handle them well on a recommender system or a forecast pipeline.

## Why it works for the workshop angles

For **01 accretion**, the task is a near-perfect substrate stress test because every one of the five sub-traps maps cleanly onto a substrate layer:

- Methodology drift → cured by a skill that pins the segment list, regime definition, and metric.
- Double-counting → cured by the same skill (fixed order, marginal accounting in the table format).
- Confounding with the contract → cured by a one-line trap in AGENTS.md ("speed-known: do not score what is clamped").
- Regime imbalance → cured by the skill's regime-segmentation step.
- Swap-the-model temptation → cured by the reference doc's bounded catalogue of legitimate upgrades.

So the M1→M4 spread is *legible*: the audience can read M1's report and name which of the five traps it hit, then watch M2's AGENTS.md grow exactly the line that cures it, then watch M3's skill add the procedure, then watch M4's eval verify it.

For **05 experiment**, the same task tests whether the workflow / universal-agent / bespoke tiers each handle attribution differently — a workflow can hardcode the ladder, an agent with a skill can adapt the ladder, a bespoke agent can propose a new rung. The genre fits cleanly into the controlled-variable framing of 05.

For **04 author**, the task is a candidate for the domain-expert seat: a senior vehicle dynamics engineer would author a `lateral-fidelity-triage` skill in front of the audience, with the catalogue of upgrades as the reference. The skill itself becomes the artefact.

It is a weaker fit for **02 empathy** (the context-window inspector adds less here — the per-turn token cost on this question is not the centrepiece of the story) and **03 harness-as-product** (no six-component spine is naturally visible in the task).

## Predicted M1 vs M4 spread

- **M1** — produces a credible numerical answer but trips at least one attribution sub-trap. Most likely: methodology drift (changes the regime mask between variants, or adds a preprocessing step that is folded into the "baseline").
- **M2** — fixes the contract-confounding and platform issues. Still trips on attribution discipline (no formal marginal accounting). Numbers improve.
- **M3** — produces a physically-grounded ladder with the regime breakdown. May report that one of the canonical upgrades makes things *worse*, with the physics-grounded reason. This is the "skill makes the agent more honest, not more optimistic" beat.
- **M4** — most disciplined, eval-passing, smallest variance closed *and* the only report a senior engineer would sign off on. The eval is the visible artefact that earns the disciplined report.

## The naked prompt

```
Our vehicle dynamics model already gets the speed right because we feed it the
measured speed. Where it falls short is the lateral behaviour — the predicted
yaw rate doesn't track the measured one. Improve it and quantify how much each
change contributes.
```
