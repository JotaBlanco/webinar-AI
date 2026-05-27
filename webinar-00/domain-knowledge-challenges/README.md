---
title: Domain knowledge challenges — shared across angles
summary: Library of engineering challenges that can be dropped into any webinar angle (accretion, empathy, harness-as-product, author, experiment). Each challenge has a why-this-is-hard analysis, a set of measurable success metrics, and a naked one-paragraph prompt. The prompt is what every module of every angle receives, verbatim — substrate is what differs across modules, not the question.
updated: 2026-05-27
---

# domain-knowledge-challenges

Library of engineering challenges that serve as the *question of the day* across the webinar angles. Each challenge is a markdown file. The file structure is:

1. **Frontmatter** — domain, what capabilities it tests, angle fit, **success metrics** (objective, post-hoc, do not appear in the prompt), and a naked-prompt audit checklist.
2. **The naked prompt** — short, natural-language, no methodology hints, no constraints, no scaffolding. **This is what every agent receives.** Nothing else from the file leaks into the agent context.
3. **Why this is challenging in general** — the trap catalogue. What makes the problem hard for any engineer (or any AI agent), independent of which angle frames it. Each trap pairs with the substrate element that cures it.
4. **Why it works for the workshop angles** — which substrate primitives the task tests under each angle, and what the M1 vs M4 spread should look like.
5. **Predicted M1 vs M4 spread** — what the audience should see across modules.
6. **Iteration log** — what was learned each time this challenge was run.

## The two disciplines

**Naked-prompt discipline** — never put substrate-equivalent content into the prompt. If the prompt names the metric, the regime, the platform, or the variant catalogue, you are doing the substrate's job inside the task, and the angle's claim ("substrate is the leverage") collapses. The `naked-prompt-audit` block in each frontmatter is the operational check.

**Measurable-success discipline** — every challenge must be scoreable post-hoc against domain-knowledge-grounded metrics, even though those metrics do **not** appear in the prompt. The `success-metrics` block in each frontmatter is the rubric a human (or eval skill) applies to an agent's report to compare M1 → M4.

## How to add a new challenge

1. Copy an existing `idea-NN-<slug>.md` and renumber.
2. Write the trap catalogue first — it forces honesty about what the task pressure-tests.
3. Write the success-metrics next — each metric must be derivable from the report without re-running the agent, and tied to a piece of domain knowledge the agent had to reach for.
4. Write the prompt last and *strip*. Default rule: if you can delete a sentence without making the task ambiguous about its *goal*, delete it. Then run the naked-prompt audit.

## Canonical schema

```yaml
---
title: ...
slug: ...
domain: ...                    # vehicle-dynamics, ...
tests:                         # controlled vocab — bundle of capabilities tested
  - attribution-discipline
  - regime-segmentation
  - operating-contract
  - metric-selection
  - truth-channel-discovery
  - data-provenance
  - failure-repro
  - tradeoff-framing
best-fit-angles: [01-accretion, 04-author, 05-experiment]
weak-fit-angles: [02-empathy, 03-harness-as-product]
success-metrics:               # post-hoc rubric — never appears in the prompt
  - id: <stable-id>
    type: binary | numeric
    rubric: <what the assessor checks>
    evidence-in-report: <how to verify from the report alone, without re-running the agent>
    threshold: <numeric only — e.g. "< 0.15">
naked-prompt-audit:            # all five must be false
  metric-named: false
  platform-named: false
  contract-named: false
  catalogue-suggested: false
  scoring-procedure-suggested: false
---
```

Body sections, in order: **The naked prompt** → **Why this is challenging in general** (trap table: Trap | What goes wrong | Substrate cure | Visible artefact in M1) → **Why it works for the workshop angles** → **Predicted M1 vs M4 spread** → **Iteration log** (append-only; one entry per angle/iter, noting prompt variant used, traps tripped at M1, surprises).

## Index

| # | Slug | Domain | Tests | Best fit angles |
|---|---|---|---|---|
| 01 | `idea-01-lateral-attribution.md` | vehicle-dynamics | attribution-discipline, regime-segmentation, operating-contract, metric-selection, truth-channel-discovery | 01 accretion, 04 author, 05 experiment |
