---
title: Idea 01B — Generic lateral improvement
summary: Same engineering goal as Idea 01, but the prompt is stripped of every methodological hint — no metric named, no platform named, no contract named, no variant catalogue suggested. The agent must reach for the substrate not only to do the work well, but to figure out what "doing the work" even means.
genre: numerical attribution
derived-from: idea-01 (L1+L2 hardening from the iter-1 retro)
best-fit-angles: [01-accretion, 04-author]
---

# Idea 01B — Generic lateral improvement

## Why this is challenging in general

Idea 01 is hard because *attribution* is hard. Idea 01B is hard because **the question is under-specified on purpose**, and most of the engineering work is in *constituting the problem* before solving it. This is much closer to what real engineering looks like.

Five things are deliberately not given:

1. **What "better" means.** No metric is named. RMSE? MAE? Peak error? % time within tolerance? Each metric privileges a different upgrade and produces a different ladder. Picking the right metric is itself an engineering decision the task does not relieve you of.

2. **Which dataset has truth.** Multiple data sources sit in the repository. Some have measured-vs-predicted truth channels; others have only predictions (the truth was never decoded). An agent that defaults to the most familiar-sounding source (more segments, more famous brand) will produce confident-looking metrics that are *not measuring what they claim to measure*. This is one of the most common failure modes in real production telemetry: claiming accuracy on a channel where the ground truth was never observed.

3. **What the model is actually doing.** The model has an operating contract — parts of its state are clamped to measured values, parts are predicted. The contract is not in the prompt. An agent that doesn't read the source code can produce a report claiming high fidelity on a channel that is *clamped*, which is technically true and operationally meaningless. The contract is a property of the *implementation*, not of the *idea* of vehicle dynamics; you discover it by reading code or you don't discover it.

4. **Which upgrades are legitimate.** No catalogue of model variants is suggested. The agent must propose its own ladder. A weak agent proposes a single big leap (KS → neural network) and reports aggregate improvement, losing all attribution. A strong agent proposes a fine-grained ladder. A *very* strong agent recognises that some upgrades are not legitimate within the contract (e.g. unclamping a clamped channel "improves" prediction by definition).

5. **What "contribution" means.** Marginal vs Shapley vs leave-one-out vs ablation — all valid attribution schemes, all producing different numbers. The natural failure mode is to just run the variants in series and credit each with its RMSE drop, which double-counts whenever two upgrades address overlapping residual structure.

These traps generalise. **Sub-trap 1** (metric selection) is the bias-variance question in disguise — the harder the underlying problem, the more the choice of metric drives the answer. **Sub-trap 2** (truth-channel discovery) shows up every time a data scientist runs a model against a dataset they didn't collect. **Sub-trap 3** (implementation-vs-spec contract) is the bug that takes down most production ML systems on the day a "trivial refactor" silently changes what the model is conditioning on. **Sub-trap 4** is the "vibe shipping" anti-pattern. **Sub-trap 5** is the half-life of every aggregate metric reported in any ML paper.

A naive agent on this prompt will produce a plausible report that gets at least three of the five wrong, and will not flag any of them. The substrate's job is not to make the agent smarter; it's to make those failures *visible*.

## Why it works for the workshop angles

For **01 accretion**, this is the harder, more visceral variant of Idea 01. The M1 → M2 jump is bigger and more legible because M1 doesn't just produce a slightly less rigorous attribution — it produces a report that may be measuring the wrong thing entirely. The accretion arc becomes "watch the same agent stop measuring the wrong thing", which is a stronger pedagogical beat than "watch the same agent's attribution discipline improve".

For **04 author**, this is the right task because the substrate the domain expert writes *is* the contract clarification, the truth-channel matrix, and the variant catalogue. The author skill becomes the answer to the under-specification, and the audience watches the expert seat turn an ambiguous question into a sharp one.

For **02 empathy** and **03 harness-as-product**, this task is harder to fit because the under-specification angle is not what those angles centre. The M1 report's *plausible wrongness* is the lesson here, and it requires the substrate-vs-no-substrate spread to land.

## Predicted M1 vs M4 spread

- **M1** — high risk of picking the wrong data source. Likely to default to the platform with more segments or more recognisable brand, miss the absence of a truth channel, and either silently fake a metric (self-consistency) or report a metric whose physical interpretation it doesn't understand. May claim longitudinal fidelity that is trivially true by clamping. The report looks credible at a glance and is wrong in a way that requires domain knowledge to spot.
- **M2** — fixes the data-source question instantly via the truth-channel matrix in `AGENTS.md`. Fixes the clamping question via the operating-contract section. Still trips on attribution discipline (variant ladder under-specified, no formal marginal accounting). Numbers are real; methodology is fuzzy.
- **M3** — produces a ladder grounded in the catalogue. The attribution is honest. The agent may report unflattering findings (e.g. a canonical upgrade making things worse) and explain them physically.
- **M4** — most disciplined, eval-passing, defensible. The eval rejects reports that don't acknowledge the contract or that latch onto the wrong channel.

The spread is wider than Idea 01's because the M1 failure mode is now *categorical* (measuring the wrong thing) rather than *quantitative* (measuring the right thing with sloppy methodology).

## The naked prompt

```
The lateral predictions from our vehicle model aren't as good as they should be.
Make them better, and tell me how much each change you made contributed to the
improvement.
```
