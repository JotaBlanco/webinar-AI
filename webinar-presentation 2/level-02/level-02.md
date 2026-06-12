# Level 02 — Skills

---

## Slide 1 — Section opener

**02**

**LEVEL 02**

**SKILLS**

---

## Slide 2 — Definition

**Skill** *(noun)*

A skill is a folder the agent can load on demand. Inside: metadata that says when to use it, instructions that say how, scripts that do the work, and any assets the work needs. The agent reads the metadata at startup; the rest only enters context when the skill is judged relevant.

---

## Slide 3 — The skills shelf, built up

Animated diagram. Each frame adds one element to the previous frame. The starting frame is the final state of Level 01's agent loop, so the audience watches the harness *grow* rather than seeing a new picture.

**Frame 1 — The Level 01 loop, in grey.**
The completed Level 01 diagram fades in, rendered in greyscale: **Human ↔ LLM Call → Action (tools) → Environment (data, code) → Feedback → LLM Call → Stop**. *Caption (optional):* "where we left off."

**Frame 2 — System Prompt surfaces.**
A new container appears above **LLM Call**, in colour: **System Prompt**. A short arrow connects it down into **LLM Call**. *Caption (optional):* "the place instructions enter the loop."

**Frame 3 — The skills/ folder appears.**
A new box materialises beside **System Prompt**: **skills/**, drawn as a folder. Empty for now. *Caption (optional):* "where procedural knowledge lives."

**Frame 4 — Skills populate.**
Inside **skills/**, ten small rectangles materialise — one per skill — each rendered as a slim header card showing only its name and a metadata block (`description`, `when-to-invoke`, `when-NOT-to-invoke`).

**Frame 5 — Metadata flows in.**
Dashed lines fan from each skill's *metadata* into **System Prompt**. *Caption (optional):* "metadata loads every turn — cheap, ~53 tokens each."

**Frame 6 — One skill activates.**
The agent ticks. One skill lights up. Its *body* — the instructions, the script descriptions, the warnings — slides into **System Prompt** along a solid line. *Caption (optional):* "the body loads only when the task matches."

**Frame 7 — The script reaches the environment.**
The active skill's script flows along the existing **Action** arrow, through **tools**, into **Environment**. *Caption (optional):* "skills act through the same tools."

### Final state — matches the dictionary entry on slide 2

The fully assembled diagram is the picture of slide 2's words:
- **skills/** — the folder the agent can load on demand.
- **metadata** (dashed lines) — read at startup, always in context.
- **body** (solid line) — only enters context when the skill is judged relevant.
- **script → tools → Environment** — skills act through the same loop you saw in Level 01.

The Level 01 loop is preserved unchanged underneath; nothing about the agent's machinery had to be replaced to add the skills layer. That's the point.

*Source: Anthropic Engineering — Equipping Agents for the Real World with Agent Skills, December 2025; Zhang & Murag — Don't Build Agents, Build Skills Instead, AI Engineer Code Summit late 2025 — https://www.youtube.com/watch?v=CEvIs9y1uog*

---

## Slide 4 — References (carousel)

Carousel of two cards. Each card: thumbnail + title + author/venue + 2–3 takeaway bullets. Card content below.

### Card 1 — *Don't Build Agents, Build Skills Instead*

**Author / venue.** Barry Zhang & Mahesh Murag (Anthropic) — AI Engineer Code Summit, late 2025.
**Link.** https://www.youtube.com/watch?v=CEvIs9y1uog
**Thumbnail.** [level-02/dontbuildagents.jpg](level-02/dontbuildagents.jpg) *(to be added)*
**Takeaways.**
- The same Anthropic speaker who gave the canonical *Building Effective Agents* talk six months earlier publicly course-corrects: **one universal agent + a library of skills** beats one bespoke agent per domain.

---

### Card 2 — *The New Code*

**Author / venue.** Sean Grove (then OpenAI alignment) — AI Engineer World's Fair, June 2025.
**Link.** https://www.youtube.com/watch?v=8rABwKRsec4
**Thumbnail.** [level-02/thenewcode.jpg](level-02/thenewcode.jpg) *(to be added)*
**Takeaways.**
- *"Code is a lossy projection of intent; the specification is the lossless source."* The audience hears the same idea Anthropic ships as Skills coming from the other major frontier lab, with independent intellectual roots.
- OpenAI's *Model Spec* and Anthropic's *Skills* are the **same primitive** — versioned, clause-addressable markdown authored by domain experts that compiles to documentation, evaluations, prompts, and behaviour. The pattern is now the field's, not one vendor's.

---

## Slide 5 — How to write a skill: anatomy of a SKILL.md

A real example from this project — `module-2.v3/skills/residual-structure/SKILL.md`. The skill diagnoses what is *left* in a fitted model's residual and returns a verdict. We chose this one because every load-bearing metadata field is visible, and because the `description` itself teaches the principle the slide is about.

```yaml
---
name: residual-structure
description: After a fit, characterise what's LEFT in the residual —
  temporal autocorrelation at multiple lags, Pearson correlation with
  each input feature AND its first time-derivative, sign-asymmetry in δ.
  Returns a per-platform **verdict** — either "noise_floor" (stop;
  you're done) or "structure_detected" with a specific reason
  ("residual autocorrelated at lag 6 → try a τ·d(δ)/dt term"). Use as
  the bridge between fit-model and "is V2 worth building?". This is
  the diagnostic the v2 cohort silently lacked — almost everyone
  shipped V1 understeer; the one agent who didn't (m2-agent-05,
  +51.5% yaw) saw exactly this autocorrelation signature and added
  a steering-rate lead.
when-to-invoke: After running `fit-model` and `score-model`, when
  you are trying to decide whether your current model has more headroom
  or you are at the noise floor. Especially when yaw RMSE has stalled
  and you do not know whether to ship or keep iterating.
when-NOT-to-invoke: Before any fit (run scoring-model first — you
  need a fitted predict_fn). To see route-level bias (use route-bias).
  To plot residual vs one feature (use inspect-residuals).
load-cost: ~210 tokens metadata, ~500 tokens body.
---
```

### Three annotations the audience should leave with

**Annotation A — `description` carries judgement, not mechanics.**
Notice what's described: not what the skill *is* (a script that runs autocorrelation and Pearson correlations), but what *signal* it produces — *a verdict* — and *why* the verdict matters. The description even names a failure mode: the V2 cohort silently shipped V1 understeer because nobody was looking at residual structure; the one agent who looked won by 9%. A skill that wraps a function call isn't worth the abstraction. A skill whose `description` names the thing only an expert would have known to look for — that's where your organisation's expertise lives.

**Annotation B — `when-NOT-to-invoke` does the routing.**
Three explicit redirects in twelve words: *"To see route-level bias, use route-bias. To plot residual vs one feature, use inspect-residuals."* Without these lines, the agent guesses which skill to load; with them, the agent routes. The v1→v3 evolution of this template cut cohort variance from σ 2.8% to σ 1.4% almost entirely by sharpening this field. Metadata's job is not to *describe* the skill — it is to help the agent *choose correctly* under progressive disclosure.

**Annotation C — `load-cost` makes progressive disclosure budgetable.**
~210 tokens of metadata, ~500 tokens of body. The metadata is paid every turn the agent thinks; the body is paid only when this skill activates. Without this line, the engineer authoring the toolkit has no way to reason about the cost of adding the eleventh skill — or the twentieth. Skills are an *economics* play as much as an architectural one, and `load-cost` is the receipt.

### The lesson

The four fields above are the whole interface. Get `description` to carry judgement, get `when-NOT-to-invoke` to actively redirect, and price the skill in `load-cost`. Everything else is style.

*Source: internal — `webinar-AI/module-2.v3/agent-01/skills/residual-structure/SKILL.md`.*

---
