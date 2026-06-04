# Level 03 — Domain Knowledge

---

## Slide 1 — Section opener

**03**

**LEVEL 03**

**DOMAIN KNOWLEDGE**

---

## Slide 2 — Definition

**Domain knowledge** *(noun)*

A short markdown document the agent loads on demand. It carries the judgement the codebase can't — the traps prior work hit, the levers worth pulling, the *why* behind the rule, with a worked example. Frontmatter tells the agent when to load it; the body only enters context when the moment matches. Every new failure your team sees becomes a new line.

*Sources: Mitchell Hashimoto — My AI Adoption Journey, Feb 2026 (the ratchet method); Sean Grove — The New Code, AI Engineer World's Fair 2025 (spec as lossless source of intent); BettaTech — ¿Qué es esto del Harness Engineering?, 2026 (guides vs sensors; AGENTS.md as harness substrate).*

---

## Slide 3 — The reference shelf, built up

Animated diagram. Each frame adds one element to the previous frame. The starting frame is the final state of Level 02's skills shelf, rendered in greyscale, so the audience watches the harness grow rather than seeing a new picture.

**Frame 1 — The Level 02 shelf, in grey.**
The Level 02 final state fades in, greyscale: **Human ↔ LLM Call ← System Prompt + skills/ → Action (tools) → Environment (data, code) → Feedback → LLM Call → Stop.** *Caption (optional):* "where we left off."

**Frame 2 — The references/ folder appears.**
A new box materialises beside **skills/**, in colour: **references/**, drawn as a folder. Empty for now. *Caption (optional):* "where judgement lives."

**Frame 3 — Reference docs populate.**
Inside **references/**, six small rectangles materialise — one per reference doc — each rendered as a slim header card showing only its filename and a metadata block (`description`, `when-to-load`, `load-cost`).

**Frame 4 — Metadata flows in.**
Dashed lines fan from each reference's *metadata* into **System Prompt**, alongside the existing skill-metadata lines from Level 02. *Caption (optional):* "metadata loads every turn — cheap."

**Frame 5 — One reference activates.**
A skill in **skills/** ticks. The reference its `when-to-load` matches lights up next to it. The reference's *body* — the worked example, the failure-mode index — slides into **System Prompt** along a solid line. *Caption (optional):* "the body loads only when the moment matches."

**Frame 6 — The ratchet appears.**
A new dashed arrow loops from **Feedback** (the environment's reply) back into the active reference, with the label *"a new line per failure"*. *Caption (optional):* "the reference learns. Every recurring failure becomes a new bullet."

### Final state — matches the dictionary entry on slide 2

The fully assembled diagram is the picture of slide 2's words:
- **references/** — the folder of short markdown documents the agent can load on demand.
- **metadata** (dashed lines) — read every turn; the agent decides whether the body is worth pulling.
- **body** (solid line) — only enters context when the moment matches.
- **ratchet** (loop from Feedback) — every failure becomes a new line; the reference accumulates the team's judgement over time.

The Level 02 shelf and the Level 01 loop are preserved unchanged underneath. References are an additive layer over skills, the same way skills were an additive layer over the bare agent. Nothing about the agent's machinery had to be replaced to add the knowledge layer. That's the point.

*Source: internal — Module 3 template at [`webinar-meta/webinar-00-template-m3.v2/`](../../webinar-meta/webinar-00-template-m3.v2/). See its [`README.md`](../../webinar-meta/webinar-00-template-m3.v2/README.md) and [`AGENTS.md`](../../webinar-meta/webinar-00-template-m3.v2/AGENTS.md) for the design rationale.*

---

## Slide 4 — References

A single reference card.

### Card 1 — *My AI Adoption Journey*

**Author / venue.** Mitchell Hashimoto (HashiCorp co-founder; mitchellh.com) — personal essay, February 2026. Synthesised into the *harness engineering* vocabulary by BettaTech (Spanish-language YouTube, late April 2026).
**Link.** https://mitchellh.com/writing/my-ai-adoption-journey
**Thumbnail.** [level-03/hashimoto.jpg](level-03/hashimoto.jpg) *(to be added)*
**Takeaways.**
- The **ratchet method**: every agent mistake gets engineered out *structurally* — in AGENTS.md, in a reference doc, in a tool wrapper — never just re-prompted away. Failures are inputs to the next iteration.
- *"AGENTS.md is the changelog of every mistake your agents have made, written in the imperative."* The same loop applies to every markdown artifact in the harness — including the domain-knowledge references.

---

## Slide 5 — How to write a reference: four mini-anatomies

Four small example panels, one per reference file from `module-3.v2/references/`. Each one illustrates a different principle the level wants to land. Together they cover the whole interface.

### Panel A — `anti-patterns.md`: the description carries judgement, not mechanics

```yaml
---
name: anti-patterns
description: Common ways prior work on this task has gone wrong.
  Lead with these — most of them are not obvious from the data alone.
when-to-load: Before you settle on a fitting procedure or evaluation
  slice. Useful as a checklist after you have a working model and want
  to know what blind spots to look for.
load-cost: ~600 words.
---

## The legal cousin — per-segment δ₀ from input channels
(this is THE winning move on the right platforms)

This is the single highest-leverage move on this dataset. In the most
recent m3 cohort, the three top-tier agents all shipped it; the three
bottom-tier agents all didn't — and the gap was +8 pts yaw / +15 pts
CTE between tiers, with model form otherwise identical.
```

**The lesson.** The frontmatter `description` names the *role* of the doc, not its contents — *"common ways prior work has gone wrong."* The body opens with a worked example whose first paragraph is **cohort evidence** — not a principle, an outcome with numbers attached. Grove's framing applies: **the reference is the lossless source of judgement.** The code that implements δ₀ correction is a lossy projection of the *insight* that bottom-tier agents reliably miss it. The reference carries the insight; the code carries the implementation.

---

### Panel B — `exploration-discipline.md`: the reference as protocol

```yaml
---
name: exploration-discipline
description: Protocol for naming ≥5 alternatives (at least 3 different
  model structures) before committing to one, plus the EXPERIMENTS.md
  log convention. Prevents silent re-convergence on the same approach
  that prior cohorts piled up on.
when-to-load: At the start of a fresh task, before your first fit.
  Re-read whenever you're tempted to "just iterate on the current model".
---

Every EXPERIMENTS.md entry MUST carry a `Rung: 0|1|2|3|orthogonal`
tag. The `pre-flighting-final-model` skill enforces at least one
`Rung: 1+` or `Rung: orthogonal` entry before the bundle can ship.
```

**The lesson.** A reference doesn't have to *teach* — it can **prescribe**. This one is a procedure: name five alternatives, log them, tag the rung, and the harness will refuse to ship if you skipped the climb. That last sentence is the **ratchet** in action — a prior cohort failed (every agent piled up on rung-0 refinements), so the harness was modified to *prevent* that failure from recurring. The reference doc is the human-readable face of the same change. **References and skills co-evolve with the failures they exist to prevent.**

---

### Panel C — `dynamics-formulations.md`: the living reference

```yaml
---
name: dynamics-formulations
description: V0 documented in full plus sketches of higher-rung
  formulations (linear dynamic ST with slip angles, nonlinear tyre,
  multi-body). Living doc — append your formulation here when you
  ship one past V0.
when-to-load: When choosing a model structure, or when residual-structure
  flags `structure_detected` and you need to know what rung-1 looks like.
---

# Minimum viable rung-1 attempt
A ~30-line code scaffold (Euler integration, fix all params from
carParams except C_αf, fit per platform). The cost-to-attempt is
lower than past cohorts assumed.
```

**The lesson.** Some references are **append-only catalogues** — every agent that ships a successful new formulation adds an entry. This is the artifact-level analogue of NC-21 (skill files as the unit of recursive self-improvement) and NC-3 (the self-improving harness). The reference grows as the team's vocabulary for the problem grows. *Any markdown artifact in the harness can learn this way* — AGENTS.md, individual skills, and references all participate in the same ratchet, at different grains.

---

### Panel D — `two-kpi-tradeoff.md`: the failure-mode index

```yaml
---
name: two-kpi-tradeoff
description: How yaw-rate RMSE and CTE RMSE relate. Two-step diagnostic
  for "yaw improved but CTE stuck". Worked example: per-platform
  bias-spread check.
when-to-load: After you have a working model and want to interpret
  your numbers.
---

## Failure-mode index

- ☐ Yaw RMSE improved >30% but CTE barely moved → check per-platform
      signed bias; a symmetric error distribution survives RMSE
      improvements but ships as drift.
- ☐ Pooled score improved, per-platform got worse on one → you fit
      pooled but evaluated pooled; check the per-platform table.
- ☐ Dev RMSE matches train RMSE exactly → you split at the sample
      level inside a segment (route leakage). Re-split.
```

**The lesson.** Every reference closes with a **failure-mode index** — a checklist of *"you'll see this if…"* patterns. This is the Husain pattern from production trace analysis, applied at authoring time: the moment a failure has surfaced often enough to characterise, it earns a checkbox here. The index is what makes the reference useful at the *moment of decision*, not just at the *moment of reading*. The agent runs through it after every fit; the user does too.

### What the four panels together say

The four fields of the frontmatter (`name`, `description`, `when-to-load`, `load-cost`) plus the closing failure-mode index are the whole interface. Inside that interface a reference can be a **diagnosis** (Panel A), a **protocol** (Panel B), a **catalogue** (Panel C), or a **checklist** (Panel D) — usually some mix. What it cannot be is a generic principle without a worked example. Every paragraph either carries a number from a real cohort, prescribes an action, or describes a failure you'll recognise. Everything else is style.

*Source: internal — [`webinar-meta/webinar-00-template-m3.v2/references/`](../../webinar-meta/webinar-00-template-m3.v2/references/).*

---
