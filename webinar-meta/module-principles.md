---
title: Principles Behind Each Module — What Actually Moved the Needle
summary: Synthesis of the principles behind Modules 1–3, grounded in the latest canonical grade (60-agent cohort, run 20260601-120739), the AI-axis NC framework, and current reputable external sources. For webinar prep.
audience: engineering webinar — "AI for engineering" thesis
updated: 2026-06-01
---

# Principles behind each module — what actually moved the needle

## The thesis, in one line

On engineering tasks, the gains come from the **environment, scaffolding, and harness you build around the model** — not from the model itself. The model is a commodity; the harness is the moat. This is now the field consensus, not a Quix opinion: the paradigm shifted **prompt engineering → context engineering → harness engineering** between 2022 and 2026, and frontier labs converged on the same primitive (Anthropic's Skills, OpenAI's Model Spec) from independent roots.

The three modules are three layers of that harness, tested on the same task with the same model:

- **Module 1** — the bare agent: a capable model with permissions, tools, data, and a task prompt. Think Claude in an IDE.
- **Module 2** — Module 1 **+ a skills toolkit** (procedural recipes the agent loads on demand).
- **Module 3** — Module 2 **+ domain-knowledge references** (the hard-won judgement of people who've done this task before).

## The evidence (canonical grade, 60 agents, identical task and model)

Every family ran the *same* task prompt against the *same* held-out pool (534 segments), scored against the *same* V0 baseline. The only thing that changed between families is the harness. Improvement is vs V0 on two KPIs — yaw-rate RMSE (instantaneous fidelity) and cross-track-error RMSE (cumulative trajectory drift).

| Family (harness) | yaw Δ% (mean ± σ) | CTE Δ% (mean ± σ) | What changed |
|---|---|---|---|
| Module 1 — agent + prompt | +48.0% ± 2.8% | +54.9% ± 2.3% | nothing (baseline harness) |
| Module 2 — + skills | +48.6% ± 1.7% | +55.1% ± 2.7% | 10-skill toolkit |
| Module 2.v3 — + skills (tuned) | +49.5% ± 1.4% | +57.3% ± 1.4% | same skills, sharper metadata + warnings |
| Module 3 — + domain knowledge | +52.3% ± 3.3% | +61.3% ± 6.4% | 6 reference docs (early version) |
| Module 3.v2 — + domain knowledge (tuned) | **+56.5% ± 0.6%** | **+72.2% ± 0.3%** | docs name the winning move + exploration policy |

Read the **σ column** as carefully as the mean. That spread is the whole story.

## The honest headline: the layers do different jobs

The naive pitch — "each layer adds a few more points" — is *not* what the data shows, and the real story is more interesting and more credible to an engineering audience:

**Skills mostly buy you reliability, not a higher ceiling.** Going from Module 1 to Module 2 barely moved the *average* score (+48.0% → +48.6% yaw). What it did move was the *variance*: yaw σ fell from 2.8% to 1.4%, and the worst agent in the cohort climbed off the floor. The median Module 1 agent already rediscovers the core physics (understeer + first-order lag) from a bare prompt — that's how good frontier models are now. Skills don't teach it something it can't find; they make every run find it, package the result correctly, and stop catching the avoidable failures (the one import_failed agent, the silently-skipped platform, the deliverable that doesn't match contract).

**Domain knowledge raises the ceiling *and* collapses variance.** Module 3.v2 is the only family that breaks out: +56.5% yaw / +72.2% CTE, with σ of 0.6% / 0.3%. Nearly every agent converged on the *same* near-optimal CTE (~70.6 m). That didn't happen by accident — the reference docs explicitly name the single highest-leverage move on this dataset (per-segment steering-offset estimation from input channels) and tell agents the prior cohort's top-three all shipped it and the bottom-three all missed it. Hand the cohort the hard-won insight and the whole cohort clears the bar.

So the webinar arc is: **Module 2 lifts the floor, Module 3 lifts the ceiling.** Both matter, for different reasons.

---

## Module 1 — the agent (model + permissions + prompt)

*What you're presenting: a capable model with access to data, code, and tools — agentic, IDE-style. The starting point, not the destination.*

**Principle 1 — An agent is just environment + tools + system prompt.** Everything else (memory, sub-agents, planners) is downstream optimisation. Nail the three core pieces before adding anything. (NC-7)

**Principle 2 — Frontier models are genuinely good now — that's the premise, not the punchline.** The bare-agent cohort already hit +48% / +55% and 10/10 ran clean. The model finds the physics. This is what lets you make the honest argument that the *remaining* gains live in the harness, not in a bigger model. Don't undersell Module 1 — its strength is exactly what sets up the thesis.

**Principle 3 — But the bare agent is a poltergeist: powerful, and unbounded.** It can move things in the world but without rails. The variance (σ 2.8%, worst agent +40%, one outright import failure) is the visible cost of no harness. Every later module is about building the lamp around the genie. (NC-1, NC-13)

**Principle 4 — "Use the computer in the dark."** The agent solves the task with only what's in its context window — and that window degrades long before it's full ("context rot": measurable degradation by ~50k tokens on a 200k model; Horthy's empirical smart/warm/dumb zones put the inflection near 40% fill). The bare agent has no help managing this. (NC-8, NC-28)

---

## Module 2 — + skills (defining procedural recipes properly)

*What you're presenting: how to define skills well. Use module-2.v3 — the tuned skill set.*

The toolkit is 10 skills — `score-model`, `fit-model`, `residual-structure`, `route-bias`, `compare-models`, `inspect-residuals`, `visualise-segment`, `make-train-dev-split`, `load-segments`, `pre-flight-final-model`. What makes them work as a teaching example:

**Principle 5 — A skill is a folder of metadata + instructions + scripts, loaded by progressive disclosure.** The agent reads only the *metadata* of all skills at startup (cheap), and pulls a skill's full body into context only when the task matches. This is the technique that keeps a large knowledge base usable inside a small context window. The economics are stark: an always-loaded `AGENTS.md` costs ~944 tokens *every turn*; the equivalent skill costs ~53 (metadata only) until invoked. (NC-12, NC-19; Anthropic Agent Skills, Dec 2025)

**Principle 6 — Write the metadata for routing, not for description.** Every SKILL.md here leads with a precise `description`, a `when-to-invoke`, *and* a `when-NOT-to-invoke` that points at the correct sibling skill ("you want to compare two models → use compare-models"). The metadata's job is to help the agent *choose* correctly under progressive disclosure. The tuning from v1→v3 was almost entirely sharpening this routing layer — and that's what dropped variance.

**Principle 7 — Skills carry judgement, not just mechanics.** `score-model` doesn't just return numbers; it puts a **signed-bias warning at the top** because "CTE is bias-dominated — look at this before you ship." `fit-model` opens with co-collapse / overfit / stuck-on-bound warnings the optimiser can't see itself. The skill encodes *what an expert would notice*, not just *how to run the computation*. This is why skills raise the floor: they stop the predictable mistakes before they happen.

**Principle 8 — Skills are designed to chain, not fork.** The toolkit ships a "suggested loop": score → read the bias check → fit → diagnose the residual → re-score. They compose into a workflow rather than presenting ten independent buttons.

**Principle 9 — Author skills by walking the workflow first, then crystallising.** The reliable recipe: drive the agent through the task manually, correct in real time; only after one clean end-to-end run, ask it to crystallise the run into a SKILL.md; then run it on new cases and feed failures back. ~5 iterations to production-reliable. Domain experts can run the first two steps — an engineer isn't in the critical path. (NC-18, NC-11)

**Principle 10 — Skills vs MCP: judgement vs connectivity.** When you hit a new workflow, ask whether the gap is *connectivity* (→ MCP server) or *judgement/procedure* (→ skill). Most real workflows need both. (NC-10)

**The honest caveat to state out loud:** skills barely moved the *average* here. Their value is reliability — tighter variance, a higher floor, correct packaging, fewer silent failures. That's a real and sellable benefit (it's the difference between a demo that `works.any()` and a product that `works.all()`), but don't claim skills alone will make a good model great.

---

## Module 3 — + domain knowledge (adding hard-won judgement properly)

*What you're presenting: how to add domain knowledge well. Use module-3.v2 — the family that actually broke out.*

Module 3 adds six reference docs on top of the Module 2 skills: `anti-patterns.md`, `approach-menu.md`, `ceiling-moves.md`, `dynamics-formulations.md`, `exploration-discipline.md`, `two-kpi-tradeoff.md`. This is the layer that moved the ceiling — and the *how* is the lesson.

**Principle 11 — Name the single highest-leverage move, and prove it with cohort history.** `anti-patterns.md` doesn't just list pitfalls; it says plainly: per-segment δ₀ estimated from input channels is *the* winning move on this dataset — "the three top-tier agents all shipped it; the three bottom-tier agents all didn't — and the gap was +8 pts yaw / +15 pts CTE, model form otherwise identical." That single, evidenced sentence is most of why the v2 cohort converged at the ceiling. Domain knowledge works when it transfers a *specific, prioritised, evidenced* insight — not a generic checklist.

**Principle 12 — Encode judgement as loadable references with their own metadata and load-cost.** Each reference doc has frontmatter: `when-to-load`, and an explicit `load-cost` (~600 words, ~1000 words). The agent is told *when* a doc earns its place in context and *what it costs* — progressive disclosure applied to knowledge, not just tools. Domain knowledge that's always-on is just context rot waiting to happen.

**Principle 13 — Teach the metric, not just the target.** `two-kpi-tradeoff.md` explains *why* the two KPIs diverge ("a small bias hurts CTE far more than yaw RMSE — CTE is a double integral of yaw error") and gives a four-pattern diagnostic table. Agents that understand *why* a metric behaves the way it does fix the right thing; agents chasing a number tokenmax their way around it. (NC-4)

**Principle 14 — Give a map of the option space, honestly annotated.** `approach-menu.md` tags every approach `[explored]` / `[lightly tried]` / `[unexplored]` and is explicit that "unexplored" says nothing about whether it works — only that the data doesn't tell us yet. It separates *refining on your current rung* from *climbing to a more expressive model structure*, and prices each. This stops the agent from mistaking a local optimum for the global one.

**Principle 15 — Engineer-in exploration discipline against premature convergence.** The most interesting design move: prior cohorts all converged on the same safe rung-0 local optimum. So `exploration-discipline.md` *requires* naming five genuinely different approaches (≥3 different model structures) and logging at least one structural-climb attempt in `EXPERIMENTS.md` — mechanically enforced by the pre-flight skill. The shipped model can still be the safe one; what's required is that the cohort *generates evidence*. This is the ratchet method applied to a whole cohort: engineer out the systematic failure (groupthink), structurally, not by re-prompting. (NC-14, NC-3)

**Principle 16 — Domain docs are append-only and grow.** `dynamics-formulations.md` documents V0 in full and sketches the higher rungs, with an explicit instruction: when you ship a new formulation, append it so the next agent builds on your work. The knowledge base is a living artifact that compounds — the same recursive-self-improvement loop as skills, applied to domain knowledge. (NC-21)

**The payoff to land:** Module 3.v2 = +56.5% / +72.2% at σ 0.6% / 0.3%. The ceiling moved *and* the cohort converged. Hand people the genuine, prioritised, evidenced expertise — packaged so it loads only when relevant — and the whole population clears the bar.

---

## The one-slide summary

The model finds the obvious answer on its own (Module 1). **Skills make it find that answer reliably, every time, packaged correctly** (Module 2 — lifts the floor, cuts variance). **Domain knowledge tells it the non-obvious answer that experts paid for in scar tissue** (Module 3 — lifts the ceiling, and the whole cohort converges on it). Same model throughout. Everything that moved was the harness.

---

## Sources

Internal:
- Canonical grade cohort, run `20260601-120739` — `webinar-AI/_grade/20260601-120739/cohort.md`
- AI-axis NC framework — `F1/KB002/ai-axis/_README.md`
- Module harnesses — `webinar-AI/module-1/`, `module-2.v3/`, `module-3.v2/` (TASK.md, AGENTS.md, skills/, references/)

External (recent, reputable):
- [Effective context engineering for AI agents — Anthropic Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Equipping agents for the real world with Agent Skills — Anthropic Engineering](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [Agent Skills overview — Claude Docs](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
- [Context Rot: How Increasing Input Tokens Impacts LLM Performance — Chroma Research](https://www.trychroma.com/research/context-rot)
- [Harness Engineering: Why the System Around the Model Decides Agent Performance — Rajiv Shah](https://rajivshah.com/blog/harness-engineering.html)
- [From Prompts to Harnesses — Four Years of AI Agentic Patterns](https://bits-bytes-nn.github.io/insights/agentic-ai/2026/04/05/evolution-of-ai-agentic-patterns-en.html)
- [Harness, Scaffold, and the AI Agent Terms Worth Getting Right — Hugging Face](https://huggingface.co/blog/agent-glossary)
