# Level 01 — Agentic AI

---

## Slide 1 — Section opener

**01**

**LEVEL 01**

**AGENTIC AI**

---

## Slide 2 — Definition

**AI Agent** *(noun)*

An AI agent is a system that pairs a language model with three things: an environment to act in, a set of tools to act with, and a system prompt that defines the job. It runs them in a loop until the task is completed.

*Source: Barry Zhang, Anthropic — How We Build Effective Agents, AI Engineer World's Fair 2025.*

---

## Slide 3 — The loop, built up

Animated diagram. Each frame adds one element to the previous frame. Reference: the Anthropic *Building Effective Agents* diagram (Schluntz & Zhang, Dec 2024).

**Frame 1 — Human.**
A single box on the left of the canvas: **Human**. The audience starts where they already are.

**Frame 2 — LLM Call appears.**
A **LLM Call** box appears centre-left. A dashed bidirectional arrow connects **Human** and **LLM Call**. *Caption (optional):* "the model takes the job."

**Frame 3 — The loop arrows appear.**
Two curved arrows appear to the right of **LLM Call**, in empty space — the upper arrow labelled **Action** (going right), the lower arrow labelled **Feedback** (coming back). The loop is visible but has nothing to act on yet. *Caption (optional):* "this is the loop."

**Frame 4 — Environment appears.**
The **Environment** box materialises on the right, terminating both arrows. The loop is now complete: LLM Call → Action → Environment → Feedback → LLM Call.

**Frame 5 — The environment fills in.**
Inside the **Environment** box, two child elements appear: **data** and **code**. *Caption (optional):* "the environment is whatever the agent can touch — the files, the codebase, the running system."

**Frame 6 — Tools appears on the action arrow.**
A **tools** label appears on (or alongside) the **Action** arrow. *Caption (optional):* "tools are how the model reaches into the environment."

**Frame 7 — Stop appears.**
A **Stop** box appears below **LLM Call**, connected by a dashed downward arrow. *Caption (optional):* "the loop ends when the model decides the job is done."

### Final state — matches the dictionary entry on slide 2

The fully assembled diagram is the picture of slide 2's words:
- **Human** ↔ **LLM Call** — the job is given (the system prompt + the request).
- **LLM Call** → **Action** (**tools**) → **Environment** (**data**, **code**) — the model acts.
- **Environment** → **Feedback** → **LLM Call** — the loop closes.
- **LLM Call** → **Stop** — until the model says it's done.

*Source: Schluntz & Zhang, Building Effective Agents, Anthropic Engineering, Dec 2024 — https://www.anthropic.com/research/building-effective-agents*

---

## Slide 4 — References (carousel)

Carousel of four cards. Each card: thumbnail + title + author/venue + 2–3 takeaway bullets. Card content below.

### Card 1 — *How We Build Effective Agents*

**Author / venue.** Barry Zhang (Anthropic) — AI Engineer World's Fair, mid-2025.
**Link.** https://www.youtube.com/watch?v=D7_ipDqhtwk
**Thumbnail.** [level-01/thinklikeagents.jpg](level-01/thinklikeagents.jpg)
**Takeaways.**
- The minimal agent is just three things: **environment + tools + system prompt**. Everything else (memory, planners, sub-agents) is downstream optimisation — add it only when you've felt the pain it solves.
- Three rules for builders: *don't build agents for everything*; *keep it simple*; *think like your agent* — get inside its head before debugging the prompt.

---

### Card 2 — *ReAct: Synergizing Reasoning and Acting in Language Models*

**Author / venue.** Yao et al. (Princeton + Google) — ICLR 2023.
**Link.** https://arxiv.org/abs/2210.03629
**Takeaways.**
- Interleaving *reasoning traces* with *tool actions* beats either alone on reasoning, QA, and decision-making benchmarks — and it makes the model's behaviour interpretable along the way.
- This is the foundational pattern every modern "agent framework" is implementing. When you strip a 2026 agent product down to its core, this loop is what's left.
- Published as an **arXiv preprint in October 2022** — before ChatGPT shipped. The agentic loop was a research idea two months before the "agent" buzzword existed, and it has held up across every model generation since.

---

### Card 3 — *Pelicans on Bicycles*

**Author / venue.** Simon Willison (Django co-creator, simonwillison.net) — AI Engineer World's Fair June 2025 (Best Speaker).
**Link.** https://www.youtube.com/watch?v=YpY83-kA7Bo&t=227s
**Thumbnail.** [level-01/pelicans.jpg](level-01/pelicans.jpg)
**Takeaways.**
- *"Tools + reasoning is the most powerful technique in AI engineering right now."* The one-line thesis for everything that follows in this webinar.

---
