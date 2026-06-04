---
title: Module 1 — The Agent (slide outline)
summary: One slide per beat. Full Module 1 cluster from the curriculum spine — worldview (NC-1, NC-13, NC-22, NC-2), the six-bullet anatomy of what Module 1 actually is (NC-7), the underlying CS principles (ReAct, tools+reasoning, sandboxing, specification), the primed beats for later modules (NC-8, NC-24, NC-23), and the canonical-grade data that closes the module. Citation-anchored at every slide.
audience: engineering webinar — module 1
updated: 2026-06-03
---

# Module 1 — Slide Outline

**Scope.** Full Module 1 cluster per the spine in `F1/KB002/ai-axis/_README.md` open questions, plus the six-bullet anatomy of what the Module 1 setup actually is. ~15 slides. Worldview first, then anatomy, then result, then bridge to Module 2.

**Convention per slide.** Title → one-line core message → 3–5 bullets of content → "Cite:" line with the reputable source → "NC:" line linking to the AI-axis catalogue. Speaker notes are one or two sentences below.

---

## Slide 1 — Title

**Title.** *Module 1 — The Bare Agent.*
**Subtitle.** *A capable model + permissions + data + tools + a task. The starting point, not the destination.*

Speaker note. Open by naming Module 1 honestly — this is what most engineers in the audience already have access to (Claude Code, Cursor, Copilot Workspace). The interesting part is what we name on top of it.

---

## Slide 2 — NC-1 — Three levels of "AI"

**Title.** *Ghost · Poltergeist · Genie.*
**Core message.** Every AI thing you've used falls on a 3-step ladder. The whole webinar is about climbing it.

- **Ghost** — bare LLM in a chat window. Passive. No hands, no memory, no data access.
- **Poltergeist** — agent with tools but no rails. Powerful and unsafe. **Module 1 lives here.**
- **Genie in a lamp** — agent inside a harness. Same power, control layer decides what it can touch, what it remembers, when a human steps in. *The lamp is the point.*

Cite. Cassie Kozyrkov, *How to Customize Agentic AI for Your Organization*, LinkedIn Live 2025 (ghost/poltergeist + genie/lamp metaphor). Reinforced by Karpathy at Sequoia 2026: *"demo is `works.any()`, product is `works.all()`."*
NC. NC-1.

Speaker note. This slide sets the frame for the entire webinar — every subsequent module is about building a better lamp, not a bigger genie.

---

## Slide 3 — NC-13 — Agent = Model + Harness

**Title.** *Agent = Model + Harness.*
**Core message.** When an agent fails, the harness isn't finished — not the model.

- The model is the engine. The **harness** is everything else: tools, memory/state, context, planning, verification, modularity.
- 2026 vocabulary: *harness engineering* is now a named discipline with literature.
- Cultural reframe: *"my agent failed"* → *"my harness isn't finished yet."*
- Module 1 = **minimal harness** (VS Code + Claude + file/bash tools + a TASK.md). Modules 2–5 = each component, deepened.

Cite. Mitchell Hashimoto, *My AI Adoption Journey* (Feb 2026); Birgitta Böckeler & Martin Fowler on coding-assistant patterns; BettaTech synthesis (your resource #4). Also Rajiv Shah, *Harness Engineering: Why the System Around the Model Decides Agent Performance* (https://rajivshah.com/blog/harness-engineering.html).
NC. NC-13.

Speaker note. This is the technical version of NC-1. *"The lamp is the point"* lands here as an equation the audience can apply on Monday.

---

## Slide 4 — NC-22 — The frontier labs converged on the same primitive

**Title.** *Skills · Specs · AGENTS.md — same artifact, three logos.*
**Core message.** This isn't an Anthropic pattern. The whole field arrived here independently.

- **Anthropic** ships it as **Skills** + `AGENTS.md`.
- **OpenAI** ships it as the **Model Spec** (deliberative alignment — the spec compiles to model weights).
- Microsoft, Google, open-source ecosystem aligned through 2025–2026.
- The common shape: *versioned, clause-addressable markdown, authorable by domain experts, compiles to behaviour.* Whoever writes the spec is the programmer.

Cite. Sean Grove, *The New Code*, OpenAI / AIEWF June 2025 (https://www.youtube.com/results?search_query=sean+grove+the+new+code). Anthropic Engineering, *Equipping agents for the real world with Agent Skills* (Dec 2025, https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills). Zhang & Murag, *Don't Build Agents, Build Skills Instead*, AI Engineer Code Summit late 2025.
NC. NC-22.

Speaker note. This is what stops the audience dismissing the rest of the webinar as Anthropic-flavoured advice. The pattern is vendor-neutral now.

---

## Slide 5 — NC-2 — The 83 / 13 gap

**Title.** *83% want to. 13% can.*
**Core message.** The audience is not alone — most orgs are stuck on the same problem.

- Cisco 2025 *AI Readiness Index* (8,000+ senior leaders): **83%** plan to deploy AI agents within 12 months; **13%** are "fully ready" to do so.
- The gap is not model access. Everyone has the model. The gap is data accessibility, governance, and the harness around the model.
- *"The interesting part of agentic AI is not the model — it's the infrastructure around it."*

Cite. Cisco, *AI Readiness Index 2025* (verify exact publication name and link before ship — citation hygiene flag from `_README.md` open questions). Pairs with the Pfeiffer three-pillars argument (data accessibility / knowledge base / autonomous execution).
NC. NC-2.

Speaker note. Hard-numbers proof point for engineers who push back on metaphor with "show me data." Keep it to one chart, one sentence.

---

## Slide 6 — What "Module 1" actually is (anatomy)

**Title.** *The minimal agent — anatomically.*
**Core message.** Module 1 = six concrete things, no more. This is the floor of the agentic spectrum.

- **Data** — a working directory with the F1 lateral-fidelity dataset (segments, sim.csv files, V0 baseline predictions).
- **Tools** — read/write files, run bash, run Python, inspect outputs. Claude Code's built-in tool layer.
- **Permissions** — the agent may launch processes, install packages, write to `final-model/`. Sandboxed to the working directory.
- **A loop** — Claude reasons, calls a tool, reads the result, reasons again. Until done.
- **A specification** — `TASK.md` describes the job, the deliverable contract, the grading criteria.
- **A frontier model + IDE harness** — Claude (Opus/Sonnet 4.x) running locally in VS Code via Claude Code.

Cite. Module 1 working directory in `webinar-AI/module-1/agent-{01..10}/`.
NC. (anatomy slide — the principles that name each piece follow.)

Speaker note. Land this concretely — open the actual `module-1/agent-01/` folder on screen if possible. Show the audience *exactly* what's in the room before naming any principles.

---

## Slide 7 — NC-7 — The minimal agent definition

**Title.** *Environment + Tools + System Prompt. That's it.*
**Core message.** Everything else (memory, sub-agents, planners, skills, RAG) is downstream optimisation.

- Six bullets from the previous slide collapse into three categories:
  - **Environment** = working directory + permissions + sandbox.
  - **Tools** = file/bash/exec + the agentic loop that wires them in.
  - **System prompt** = TASK.md + Claude Code's defaults + AGENTS.md if present.
- *"Keep it simple"* — Barry Zhang's second rule. Don't add a piece until you've felt the pain it solves.
- Skills (Module 2) and reference docs (Module 3) are mechanisms by which **the tools and system prompt get populated dynamically** — the definition stays.

Cite. Barry Zhang, *How We Build Effective Agents*, Anthropic, AIEWF mid-2025 (your resource #2). Schluntz & Zhang, *Building Effective Agents*, Anthropic Engineering Dec 2024 (https://www.anthropic.com/research/building-effective-agents).
NC. NC-7.

Speaker note. This is the *organising principle* of Module 1. Audience leaves with a 3-word checklist.

---

## Slide 8 — The agentic loop has a name (ReAct)

**Title.** *Reason → Act → Observe → Reason. Repeat.*
**Core message.** The "agentic capability to loop" is a 2022 idea — and the foundation of everything we'll do.

- Yao et al., *ReAct: Synergizing Reasoning and Acting in Language Models* (Princeton + Google, ICLR 2023, https://arxiv.org/abs/2210.03629). Pre-dates the agent hype by two years.
- The pattern: emit a thought → emit a tool call → read the observation → emit the next thought. Loop until done.
- What's changed since 2022 isn't the loop — it's the **model quality** that makes the loop actually finish a real task.
- Modern phrasing (Hykes, AIEWF 2025): *"an agent is an LLM wrecking its environment in a loop."* Same loop. Funnier.

Cite. Yao et al. arXiv 2022 / ICLR 2023. Solomon Hykes, *Containing Agent Chaos*, AIEWF June 2025 (your resource #7).
NC. (cross-cuts NC-7 and NC-13.)

Speaker note. Spend 30 seconds on the receipt — engineers respect the paper, and it kills "is this just hype?" pushback.

---

## Slide 9 — Tools + reasoning is the unlock

**Title.** *Tools + reasoning is the most powerful technique in AI engineering right now.*
**Core message.** "Access to tools" isn't a checkbox. It is the thing that turned chat into engineering.

- A bare LLM reasons. A bare LLM with tools *acts on the world*.
- Every Module 1 agent succeeded because the loop could: read sim.csv → write a fit script → run it → read the residuals → iterate.
- 2024–2025 standardisation: **MCP** (Model Context Protocol) gave tool use a portable interface. Module 1 doesn't need it yet; Module 3+ will benefit.
- Quote-able framing: *"tools + reasoning is the most powerful technique in AI engineering right now"* — Simon Willison, AIEWF 2025 (Best Speaker).

Cite. Simon Willison, *Pelicans on Bicycles*, AIEWF June 2025 (your resource #9). Anthropic, *Introducing the Model Context Protocol*, Nov 2024 (https://www.anthropic.com/news/model-context-protocol). Anthropic Tool Use docs (https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview).
NC. NC-10 (primed; full skills-vs-MCP treatment in Module 3).

Speaker note. The non-vendor anchor (Willison) is the credibility move. Drop it as a one-line quote with attribution and move on.

---

## Slide 10 — Sandboxing is the unsexy precondition

**Title.** *Permissions + a working directory = the sandbox.*
**Core message.** The agent acts on the world. Bound the world.

- Hykes' framing: an agent is an LLM **wrecking** its environment. You want the wreckage contained.
- Four required properties of an agent environment: **isolation, customisation, multiplayer, openness**.
- Module 1's sandbox = the `agent-NN/` working directory + Claude Code's per-tool permission gates. Crude but real.
- This is also where the **lethal trifecta** lives — once an agent has data access, tools, and an exfiltration channel, it's exploitable by design. We'll come back to it.

Cite. Solomon Hykes, *Containing Agent Chaos*, AIEWF June 2025. Simon Willison, *The lethal trifecta* (https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/).
NC. NC-25 (sandbox); NC-24 primed (full treatment in Module 5).

Speaker note. Don't go deep on the trifecta here — just *name* it so it's not a surprise when it appears in Module 5.

---

## Slide 11 — Good prompting is good specification

**Title.** *The TASK.md is the program.*
**Core message.** "Good prompting" is really *good specification* — and the spec is the lossless source of intent.

- Sean Grove (OpenAI, AIEWF 2025): *"code is a lossy projection of intent; the specification is the lossless source."*
- Karpathy (Sequoia 2026): *"the context window is the program."*
- Module 1's TASK.md does the heavy lifting: states the deliverable contract (`final-model/predict.py`), the grading KPIs (yaw RMSE, CTE RMSE), the inputs/outputs, the freedom to modify or replace the harness.
- *You cannot outsource the thinking.* The engineer frames the spec; the agent executes against it.

Cite. Sean Grove, *The New Code*, OpenAI / AIEWF June 2025 (your resource #8). Andrej Karpathy, Sequoia AI Ascent 2026 keynote. Dex Horthy, *No Vibes Allowed*, AI Engineer Code Summit Nov 2025 (your resource #6).
NC. NC-22 (specifications), NC-27 (RPI loop primed).

Speaker note. Show the actual TASK.md on screen for 10 seconds. Audience sees the artifact, not just the principle.

---

## Slide 12 — Frontier models are good enough now

**Title.** *The model is not the bottleneck anymore.*
**Core message.** This is what licenses the rest of the webinar's argument.

- Module 1 canonical-grade result: **+48.0% ± 2.8% yaw / +54.9% ± 2.3% CTE** improvement over V0, 10/10 agents shipped clean. **Zero** scaffolding beyond TASK.md and the IDE.
- The model finds the physics on its own (understeer + first-order lag). It doesn't need to be *taught*; it needs to be *equipped*.
- *"The models are good now — the differentiator is the context and harness you build around them."* (Shimeles, on Greg Isenberg's podcast, April 2026.)
- Practical implication: the rest of the webinar's gains live in the harness, not in waiting for GPT-7.

Cite. Internal — canonical-grade cohort `webinar-AI/_grade/20260601-120739/`. Michael Shimeles (Ras Mic), Fabrika — *How AI Agents & Claude Skills Work*, on Startup Ideas Podcast, April 2026 (your resource #5).
NC. (worldview — supports the thesis under NC-22 / NC-13.)

Speaker note. This is the **honest** version of "the model is good now." Show the cohort table briefly. The σ matters for Module 2's argument later — flag it but don't dwell.

---

## Slide 13 — NC-8 (primed) — The computer in the dark

**Title.** *The agent solves the task with only what's in its context window.*
**Core message.** Module 1 has nothing helping it manage that window. We'll feel the limit in Module 2.

- The agent doesn't see your monitor. It sees **what tool calls returned**, in order, inside a finite window.
- Empirical degradation begins long before the window is full. Horthy's smart/warm/dumb-zone curve: **performance falls off above ~40% fill**.
- Module 1 succeeded because the task is bounded. As tasks scale up, this becomes the dominant failure mode.
- Module 2 is where we name the technique that addresses it (progressive disclosure via skills).

Cite. Dex Horthy, *Advanced Context Engineering for Agents*, Context Engineering SF late 2025. Anthropic, *Effective context engineering for AI agents* (2025, https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents). Chroma Research, *Context Rot: How Increasing Input Tokens Impacts LLM Performance* (https://www.trychroma.com/research/context-rot).
NC. NC-8, NC-28 (primed; full treatment in Module 2).

Speaker note. Don't show numbers yet. Just *name* it, plant the seed. Module 2 has the visceral demo.

---

## Slide 14 — NC-23 (primed) — How do we know it worked?

**Title.** *Without an eval, you don't have a result — you have a vibe.*
**Core message.** Module 1's +48% number is only meaningful because the grading harness exists.

- The Module 1 cohort runs against a **held-out 534-segment pool**, scored against the same V0 baseline, with the same two KPIs. The eval is the substrate.
- Without it, the entire webinar would be anecdote. With it, every claim in every later module is falsifiable.
- *Error analysis first; custom binary judges later; production-trace sampling continuously.* (Husain / Shankar / Yan converged methodology, 2026.)
- Module 5 will go deep on this. For now: the eval is the reason the rest of the talk is honest.

Cite. Hamel Husain, *Field guide to rapidly improving AI products* (https://hamel.dev/blog/posts/field-guide/). Shreya Shankar et al., *Who Validates the Validators?* (https://arxiv.org/abs/2404.12272). Applied LLMs, *What we learned from a year of building with LLMs* (https://applied-llms.org/).
NC. NC-23 (primed; full treatment in Module 5).

Speaker note. Engineers respect this slide. It says *we're not selling you a vibe.* Keep it to one slide; the deep dive is later.

---

## Slide 15 — The Module 1 result — and the honest framing

**Title.** *+48% yaw / +55% CTE, σ 2.8 / 2.3, one import failure. That's the floor.*
**Core message.** Module 1 already works. The interesting question is what *doesn't* work yet.

- The median Module 1 agent rediscovers the physics from a bare prompt. Frontier models are that good.
- What's *not* great:
  - σ of ~2.8% on yaw — the spread between best and worst agent is real.
  - One agent in 10 failed to ship (import error).
  - No agent found the **non-obvious** ceiling moves (per-segment δ₀ from input channels — Module 3 territory).
- The honest pitch: **the model finds the obvious answer. Skills make it find that answer reliably. Domain knowledge tells it the non-obvious answer.**

Cite. Internal — canonical-grade cohort `webinar-AI/_grade/20260601-120739/cohort.md`. Cross-ref `webinar-meta/module-principles.md`.
NC. (sets up the floor/ceiling story for Modules 2 and 3.)

Speaker note. Lock the "floor / ceiling" framing here — it's the spine of the next two modules. Don't oversell Module 1 *or* undersell it.

---

## Slide 16 — Bridge to Module 2

**Title.** *Module 1 is a poltergeist. Module 2 starts building the lamp.*
**Core message.** Six things we'll add starting now.

- Skills (procedural recipes loaded by progressive disclosure) → Module 2.
- Domain references (the hard-won expertise) → Module 3.
- An ops layer (managed pipelines, the runtime substrate) → Module 4 / workshop core.
- An eval discipline (custom judges + production traces) → Module 5.
- A security architecture (cut a leg of the lethal trifecta) → Module 5.
- A self-improving artifact loop (the ratchet method) → throughout.

Cite. The Module 1 cluster ends here; each item points forward to its module.
NC. NC-1 (climbing the ladder), NC-13 (deepening each component).

Speaker note. Two-sentence outro. Don't oversell what's coming — let Module 2's demo do the talking.

---

## Footer / appendix references for the deck

External, in citation order of appearance:
- Cassie Kozyrkov, *How to Customize Agentic AI for Your Organization* (LinkedIn Live 2025).
- Andrej Karpathy, Sequoia AI Ascent 2026 keynote.
- Mitchell Hashimoto, *My AI Adoption Journey* (Feb 2026).
- Birgitta Böckeler & Martin Fowler, coding-assistant patterns essays (Thoughtworks).
- Rajiv Shah, *Harness Engineering: Why the System Around the Model Decides Agent Performance* — https://rajivshah.com/blog/harness-engineering.html
- Sean Grove (OpenAI), *The New Code* — AIEWF June 2025.
- Anthropic Engineering, *Equipping agents for the real world with Agent Skills* — https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- Barry Zhang & Mahesh Murag, *Don't Build Agents, Build Skills Instead* — AI Engineer Code Summit late 2025.
- Cisco, *AI Readiness Index 2025* (verify exact pub link before ship).
- Schluntz & Zhang, *Building Effective Agents* — https://www.anthropic.com/research/building-effective-agents
- Barry Zhang, *How We Build Effective Agents* — AIEWF mid-2025.
- Yao et al., *ReAct: Synergizing Reasoning and Acting in Language Models* — https://arxiv.org/abs/2210.03629
- Solomon Hykes, *Containing Agent Chaos* — AIEWF June 2025.
- Simon Willison, *Pelicans on Bicycles* — AIEWF June 2025 (Best Speaker).
- Anthropic, *Introducing the Model Context Protocol* — https://www.anthropic.com/news/model-context-protocol
- Anthropic, *Tool Use* docs — https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview
- Simon Willison, *The lethal trifecta* — https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/
- Dex Horthy, *No Vibes Allowed* — AI Engineer Code Summit Nov 2025.
- Dex Horthy, *Advanced Context Engineering for Agents* — Context Engineering SF late 2025.
- Anthropic Engineering, *Effective context engineering for AI agents* — https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Chroma Research, *Context Rot* — https://www.trychroma.com/research/context-rot
- Michael Shimeles (Ras Mic), Fabrika — *How AI Agents & Claude Skills Work* on the Startup Ideas Podcast, April 2026.
- Hamel Husain, *Field guide to rapidly improving AI products* — https://hamel.dev/blog/posts/field-guide/
- Shreya Shankar et al., *Who Validates the Validators?* — https://arxiv.org/abs/2404.12272
- Applied LLMs, *What we learned from a year of building with LLMs* — https://applied-llms.org/

Internal:
- `webinar-AI/_grade/20260601-120739/cohort.md` — the canonical-grade cohort.
- `webinar-AI/module-1/agent-{01..10}/` — the Module 1 working directories.
- `F1/KB002/ai-axis/_README.md` — the NC catalogue.
- `webinar-meta/module-principles.md` — the parent synthesis this outline implements.

## Open citations to verify before ship

- **NC-2 / Cisco** — confirm exact 2025 *AI Readiness Index* publication name, public link, and that "83% / 13%" are the headline figures Kozyrkov cited.
- **Karpathy Sequoia 2026** — confirm the keynote title and that *"the context window is the program"* is a literal quote vs. a paraphrase.
- **Hashimoto, *My AI Adoption Journey*** — confirm the canonical link (his blog vs. a talk recording).
- **Cisco 2025 numbers vs. 2026 update** — if a 2026 follow-up exists, prefer it.
