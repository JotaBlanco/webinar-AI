---
title: Webinar task ideas — shared across angles
summary: Library of engineering challenges that can be dropped into any webinar angle (accretion, empathy, harness-as-product, author, experiment). Each idea has a why-this-is-hard analysis and a naked one-paragraph prompt. The prompt is what every module of every angle receives, verbatim — substrate is what differs across modules, not the question.
updated: 2026-05-26
---

# webinar-ideas

Library of engineering challenges that can be used as the *question of the day* across the webinar angles. Each idea is a markdown file with:

1. **Why this is challenging in general** — what makes the problem hard for any engineer (or any AI agent), independent of which angle frames it.
2. **Why it works for the workshop angles** — which substrate accretion / context engineering / harness primitives the task tests, and what the predicted M1 vs M4 spread looks like.
3. **The naked prompt** — short, natural-language, no methodology hints, no constraints, no scaffolding. **This is what every agent receives.** Nothing else from this file leaks into the agent context. The substrate of each module is what compensates (or fails to compensate) for the absence of hints.

The discipline: **never put substrate-equivalent content into the prompt.** If the prompt names the metric, the regime, the platform, or the variant catalogue, you are doing the substrate's job inside the task — and the angle's claim ("substrate is the leverage") collapses.

## How to add a new idea

1. Copy an existing `idea-NN-<slug>.md` and renumber.
2. Write the two analysis sections first — they force you to be honest about what the task pressure-tests.
3. Write the prompt last and *strip*. Default rule: if you can delete a sentence without making the task ambiguous about its *goal*, delete it. The agent must reach for the substrate to make the methodology decisions.

## Index

| # | Slug | Genre | Primary trap | Best fit angle |
|---|---|---|---|---|
| 01  | `idea-01-lateral-fidelity-attribution.md` | Numerical attribution | Disciplined ladder under speed-known contract | 01 accretion, 05 experiment |
| 01B | `idea-01B-generic-lateral-improvement.md` | Numerical attribution | Pick the platform with truth; discover the contract | 01 accretion, 04 author |
