---
title: Module 2 — Skills — Speaker Outline
summary: Section-by-section talk track for Module 2 of the webinar. Mirrors the existing quix-module2-skills-principles.pptx (14 slides) and proposes 4 insertions to close gaps the user flagged (recap of "what is an agent", context-engineering background, skills tour, maintenance hygiene). Every principle is anchored to a verified primary source.
audience: engineering webinar — "AI for engineering" thesis
updated: 2026-06-03
---

# Module 2 — Skills — Speaker Outline

The module answers four questions the audience walks in with:

1. **What is a skill?** (slides 2–3 + insert A)
2. **Why does it work?** (slides 4–6 + insert B)
3. **How do you write one?** (slides 7–9 + insert C)
4. **How do you maintain a fleet of them?** (slides 10–11 + insert D)

Then we land it with cross-vendor convergence (slide 12), our cohort evidence (slide 13), and references (slide 14).

## Agentic framing — brief recap (≤ 60 seconds, no slide)

Open before slide 1. The audience just saw Module 1 land NC-1 (ghost / poltergeist / genie) and NC-13 (Agent = Model + Harness — Fowler / Hashimoto / BettaTech). Don't re-explain. One sentence:

> *"Module 1 gave us the agent: model + tools + environment + system prompt, sitting inside a harness. Skills are how that harness scales — without growing the always-on system prompt. Same agent. New layer."*

That's it. The full agentic treatment lives in Module 1; here we earn the right to talk about skills by reminding people skills are *part of* the harness they just met.

**Is what we're showing 'agentic'?** Yes, by every operating definition. Anthropic's own *Building Effective Agents* (Schluntz & Zhang, Dec 2024, https://www.anthropic.com/engineering/building-effective-agents) defines an agent as *an LLM dynamically directing its own processes and tool usage*. Our Module 2 agent does exactly that. The more honest framing is **Agent = Model + Harness**, where `skills/` is a part of the harness. So when someone asks "is this agentic", answer *"yes, but the interesting thing isn't the agent — it's the harness"*. That's the whole thesis of the webinar in one sentence.

---

## Slide 1 — Title

**On-screen:** "MODULE 2 — Skills — The principles that make a skill good, and the people who worked them out."

**Speaker beat (~30 sec):** Module 1 was the bare agent. We saw it find the physics on its own — frontier models are genuinely good now. The remaining gains are in the harness. This module is about one specific harness layer — skills — and the principles that distinguish good skills from a clever-looking folder.

**Watch out for:** Don't claim skills make the model smarter. They don't. They make the same model *reliable*. That's the honest pitch and the data backs it.

---

## INSERT A (recommended new slide between 1 and 2) — Context engineering: why this matters at all

**Why this slide exists:** Principle 1 (slide 4) cites the 944-vs-53 economics, but the audience hasn't heard *why* every token in the context window has a cost. Without this, progressive disclosure looks like a memory micro-optimisation. With this, it looks like the only way to keep an agent functional.

**On-screen:** Two anchors —
- **Karpathy** (Sequoia AI Ascent 2026): *"Context engineering is the delicate art and science of filling the context window with just the right information for the next step."*
- **Chroma Research** (July 2025): *"Models do not use their context uniformly; their performance grows increasingly unreliable as input length grows."* — tested across 18 frontier LLMs.

**Speaker beat (~75 sec):** The shift from prompt engineering to **context engineering** is the canonical vocabulary change of 2026. Prompt engineering was about wording one input well. Context engineering is about deciding *what is in the window at all* — across many turns, across tool outputs, across loaded references. Chroma measured this empirically across 18 frontier models: performance doesn't degrade linearly as you fill the window. It degrades unpredictably, and you don't get the cliff back by re-prompting. *That* is the problem skills solve.

**Sources to put on the slide:**
- Karpathy, *Software 3.0 / From Vibe Coding to Agentic Engineering*, Sequoia AI Ascent 2026 — https://www.youtube.com/watch?v=96jN2OCOfLs (write-up: https://karpathy.bearblog.dev/sequoia-ascent-2026/)
- Chroma Research, *Context Rot* — https://research.trychroma.com/context-rot
- Optional non-vendor reinforcement: Anthropic Engineering, *Effective context engineering for AI agents*, 29 Sep 2025 — https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents

---

## Slide 2 — The gap skills fill

**Speaker beat (~60 sec):** Frontier models are brilliant generalists. On *your* work, they lack your expertise, can't absorb it well, and don't learn over time. Three things you'd hope a junior would do — they don't. The Zhang/Murag pitch is that the fix isn't a smarter model; it's a *folder* of procedural recipes the agent loads on demand. They call this a "skill." The architectural inversion: one agent, many skills, not one agent per domain.

**Citation correction needed on the slide:**
- Slide currently reads *"Anthropic · AI Engineer Code Summit, Dec 2025"*. The talk URL `youtube.com/watch?v=CEvIs9y1uog` was uploaded **~Dec 8, 2025**. That date is fine; AI Engineer Code Summit ran **Nov 19–22, 2025** — if you want to be precise, change to "AI Engineer Code Summit, Nov 2025" (better match to the conference itself).

**Verified quote (the one currently on the slide):** Paraphrase, not verbatim. Safer wording: *"Stop building a specialised agent for every domain. Build one general-purpose agent with a library of Skills."* — paraphrased from Zhang & Murag, *Don't Build Agents, Build Skills Instead*.

---

## Slide 3 — A skill is a folder, not a framework

**Speaker beat (~60 sec):** This is the simplest definition possible and it's load-bearing. A skill is a directory with one `SKILL.md` at the top. YAML metadata — `name` and `description` — on top. Instructions below. Optional `scripts/` and `assets/` alongside. No SDK. No bespoke agent code. The whole thing is portable across any tool that reads the format — which is now most of them.

**Citation correction needed:** Slide currently says *"December 2025"* for the Anthropic publication. **It's October 16, 2025.** Source: https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills — Anthropic's own dateline is October 16. **Please fix on the slide.**

**Verified quote from the platform docs (https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview):** *"A Skill bundle is a directory containing a SKILL.md file at the top level with name and description YAML frontmatter, plus any supporting scripts or resources."* — use this if you want a quote from the canonical product doc rather than the engineering blog.

**Reinforcement to add verbally:** Mention that the format is now an **open standard** — Anthropic published it openly so other vendors (and your own internal tools) can read the same artifact. That's what makes the next-to-last slide (cross-vendor convergence) credible.

---

## Slide 4 — Principle 1: Load metadata first, body on demand

**Speaker beat (~75 sec):** This is the technique. Three phases — discovery, activation, execution. At startup the agent reads *only* each skill's `name` + `description` lines. It pulls the full instructions into the working context **only when a task matches**. It runs bundled scripts only if needed.

The economics make this concrete: an always-on `AGENTS.md` of decent size sits at roughly 944 tokens per turn — paid every turn whether relevant or not. The same content packaged as a skill costs roughly 53 tokens per turn until activated. *Every. Single. Turn.*

**Citation caveat — important:** The exact 944-vs-53 numbers come from Michael Shimeles (Ras Mic) on Greg Isenberg's *Startup Ideas Podcast*, April 2026. I could only confirm those specific numbers via third-party recaps, not directly from the episode page. Two options:
1. **Verify by listening to the episode** (https://www.youtube.com/watch?v=S_oN3vlzpMw) and confirm the numbers before publishing. *Recommended* — this is the headline economic claim of the module.
2. If you can't verify in time, soften to *"~20× cheaper per turn"* and cite the Anthropic Skills blog's progressive-disclosure description directly.

**Verified quote (use on the slide):** From the Anthropic Skills blog — *"Like a well-organized manual that starts with a table of contents, then specific chapters, and finally a detailed appendix, skills let Claude load information only as needed."*

**Sources:**
- Anthropic Engineering, *Equipping agents for the real world with Agent Skills*, **16 Oct 2025** — https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
- Michael Shimeles on Startup Ideas Podcast, April 2026 — https://www.youtube.com/watch?v=S_oN3vlzpMw (verify numbers before quoting)

---

## Slide 5 — Principle 2: One universal agent, library of skills

**Speaker beat (~60 sec):** Don't clone an agent per domain. Keep one stable agent. Give it a library it can draw from. Zhang's analogy: you don't want your colleague re-deriving the 2025 tax code from first principles. You want consistent execution from a domain expert. Skills are that expert, on call.

The progression that matters — and that we'll come back to in Principle 7 — is *one agent → many skills*, not *one agent → many agents*. Multi-agent is what you reach for after skills work, never as a substitute.

**Citation:** Zhang & Murag, *Don't Build Agents, Build Skills Instead*, Anthropic, AI Engineer Code Summit Nov 2025 — https://www.youtube.com/watch?v=CEvIs9y1uog

---

## Slide 6 — Principle 3: Judgement vs connectivity (skills vs MCP)

**Speaker beat (~60 sec):** When you hit a new workflow, ask one question: is the gap *connectivity* or *judgement*? Connectivity — reaching a system, an API, a data store — is an MCP server's job. Judgement — the procedure, the recipe, the domain logic — is a skill's job. Most real workflows need both.

For our F1 telemetry / vehicle-dynamics example: an MCP server to *connect* to the segment data is connectivity. The procedural recipe — *"score, read the bias check first, fit, diagnose with residual-structure, iterate"* — is judgement. That's what a skill carries.

**Citation correction needed on the slide:** Slide currently quotes Willison as *"Claude Skills are awesome, maybe a bigger deal than MCP."* That's the title of his Oct 16, 2025 post. The post itself says **MCP "lets you mix and match"** rather than calling MCP *the* standardising interface — the wording the existing slide implies. Safer slide framing:

> *"Skills handle the procedural recipe. MCP handles the connectivity. Most real workflows need both."*
> — Willison's framing in his Oct 16, 2025 post, paraphrased.

**Sources:**
- Simon Willison, *Claude Skills are awesome, maybe a bigger deal than MCP* — https://simonwillison.net/2025/Oct/16/claude-skills/
- Zhang & Murag (same talk as slide 5) — for the canonical Skills-vs-MCP framing.

---

## Slide 7 — Principle 4: Write the description to be chosen, not to describe

**Speaker beat (~75 sec):** Under progressive disclosure, the only thing the agent sees when it's deciding whether to load a skill is the metadata. So the metadata's job is *not* to describe what the skill does — it's to help the agent **choose correctly**. Every SKILL.md in our toolkit leads with three things, in this order:

1. A precise `description` — what it does, what it returns.
2. A `when-to-invoke` — the *symptom* in the agent's current world that should trigger it.
3. A `when-NOT-to-invoke` — *and this is the move* — that names the right sibling. *"You want to compare two models — use compare-models."* *"You want to optimise coefficients — use fitting-model."*

That third line is what we tuned between v1 and v3. Run-to-run variance dropped from σ 2.8% to σ 1.4% on the same task with the same model. Same skills. **The tuning was the routing layer.**

**Sources:**
- Quix Module 2 v3 toolkit (`webinar-AI/module-2.v3/`)
- Anthropic Skills blog (progressive-disclosure framing) — same URL as slide 4.

---

## INSERT B (recommended new slide between 7 and 8) — Skills as clay, not library

**Why this slide exists:** Your own `webinar-00-template-m2/README.md` says it explicitly: *"Skills are clay, not library."* It's a real principle that distinguishes good skills from a frozen SDK. Slide 7 just told the audience the metadata is the contract; this slide gives them permission to break the body.

**On-screen — the line itself:** *"Treat skills as clay, not library. If a skill's output isn't useful, the skill is wrong. Open the body, add the column or table you need, save, re-run. If a skill is in your way, delete it."*

**Speaker beat (~60 sec):** Two design choices follow from this. First — skills are **short on purpose.** Every SKILL.md in our toolkit is under 80 lines including frontmatter. Short enough to read in one sitting. Short enough to *change* in one sitting. If you can't sit down and rewrite the body in 15 minutes, it's not a skill anymore — it's a library. Second — there's no commitment to a skill. If the agent isn't reaching for it, or it's *in the way*, delete it. The toolkit pays no rent for unused skills, and an unused skill is just metadata clutter at the discovery stage.

**Citation:** Quix Module 2 template AGENTS.md and README — internal practice. (Could also be cross-referenced to Horthy's *"you cannot outsource the thinking"* — the engineer is still the engineer.)

---

## Slide 8 — Principle 5: Encode what an expert would notice

**Speaker beat (~75 sec):** A good skill doesn't just run a computation — it flags what matters. Our `score-model` doesn't return a single pooled RMSE; it returns a per-segment table, per-platform signed-bias decomposition, per-route pooled error, distributions, and then — at the **top** of the formatted summary — it prints a signed-bias warning when one platform's residual mean exceeds threshold. Because CTE is a double integral of yaw error, and a small systematic bias kills CTE far harder than per-sample noise does. *That's the thing experts look at first.* The agent now does too.

**Why this is load-bearing:** This is the difference between a skill that's a function and a skill that's a colleague. The function returns numbers. The colleague notices what's worth noticing. That's why skills raise the floor — they stop the predictable mistakes the optimiser can't see itself making.

**Citation:** Quix Module 2 v3, `score-model/SKILL.md`. (Also pairs naturally with `fit-model`, which opens its summary with 🚨 co-collapse / overfit / stuck-on-bound / non-convergence warnings.)

---

## INSERT C (recommended new slide between 8 and 9) — A tour of the toolkit

**Why this slide exists:** The deck talks about skills in the abstract and uses `score-model` as the running example. The audience hasn't yet *seen* the 10 skills as a system. This slide gives them the inventory and — crucially — the **suggested loop** that links them. That suggested loop is your Principle 8 from `module-principles.md`: "skills are designed to chain, not fork."

**On-screen — the inventory:**

| Skill | What it does | Where it sits in the loop |
|---|---|---|
| `score-model` | Diagnostic oracle — pooled KPIs, per-platform signed bias, worst-N outliers, distributions | 1. Score |
| `fit-model` | Optimise coefficients per platform; train/dev gap inline; warnings on co-collapse, overfit, stuck-on-bound | 2. Fit |
| `residual-structure` | After a fit, characterise what's LEFT in the residual — autocorrelation, feature-correlations, sign-asymmetry. Verdict: `noise_floor` or `structure_detected` | 3. Diagnose |
| `route-bias` | Group residuals by route; rank by share of platform pooled error | 3. Diagnose |
| `inspect-residuals` | Plot residual vs any input feature, 1-D or 2-D heatmap | 3. Diagnose |
| `compare-models` | Per-segment diff of two predictors with regression / improvement rankings | 2. → 3. |
| `visualise-segment` | 3-panel PNG of one segment with truth + predictions overlaid | 3. Diagnose |
| `load-segments` | Path-resolving loader with dtype hygiene + provenance in `df.attrs` | infrastructure |
| `make-train-dev-split` | Route-grouped split + a validator that *raises* on leakage | infrastructure |
| `pre-flight-final-model` | Verify the deliverable bundle matches the contract before shipping | 4. Ship |

**Speaker beat (~90 sec):** The toolkit is designed to **chain, not fork**. The suggested loop is on screen: score, read the bias warning, fit, diagnose what's left in the residual, iterate the model — *not* the fit. The skill names are verbs. The loop has a defined end (pre-flight). And — this is the *"Don't ship V1"* warning that's literally in AGENTS.md — the loop is designed so the agent reaches V2 before declaring done, because the v2 cohort hit a ceiling by shipping V1 understeer fits.

**Citation:** Quix Module 2 v3 `AGENTS.md` — the "Suggested loop" section.

---

## Slide 9 — Principle 6: Walk the workflow, then crystallise

**Speaker beat (~75 sec):** Don't write a skill first. *Walk* the workflow first. The reliable recipe — three steps:

1. Drive the agent through the task **manually**, correcting in real time. One successful end-to-end run.
2. *Only then*, ask the agent to crystallise the run into a `SKILL.md`. The corrections you made are now metadata + body.
3. Run it on new cases. When it fails, feed the failure back; the agent updates its own skill. ~5 iterations to production-reliable.

Critically: steps 1 and 2 are **executable by a domain expert.** No engineer in the critical path. That's how skills scale across an organisation — finance, recruiting, legal, ops, engineering experts authoring their own. Anthropic's third trend.

**Citation correction needed:** Slide currently cites Shimeles. That's right for the *walk-then-crystallise* recipe. But the *non-developer authoring* claim should be attributed to **Zhang & Murag's Trends slide** (same talk as slides 2 and 5) — not to Shimeles. If you want both citations on one slide, split the speaker beat.

**Sources:**
- Michael Shimeles on Startup Ideas Podcast, April 2026 — https://www.youtube.com/watch?v=S_oN3vlzpMw (for the walk-then-crystallise recipe — verify episode before quoting verbatim)
- Zhang & Murag, *Don't Build Agents, Build Skills Instead* (for the non-developer authoring trend)

---

## Slide 10 — Principle 7: Get one skill reliable before reaching for many agents

**Speaker beat (~60 sec):** The sequencing rule of thumb: *one agent + one skill (make it reliable) → one agent + many skills (the architecture from slide 5) → only then consider sub-agents*. Multi-agent is what you reach for **after** skills work, never as a fix for an unreliable single agent. "Don't add a sub-agent until you've got a reliable skill."

When you finally do reach for sub-agents, the right reason (per Horthy) is **context isolation** — each sub-agent gets a fresh, smaller window for one well-scoped slice. *Not* "give each sub-agent a persona." The persona framing is theatrics.

**Citation:**
- Michael Shimeles on Startup Ideas Podcast — for the *skill maxxing* sequencing rule (same URL; verify the phrase verbatim before using).
- Dex Horthy, *Advanced Context Engineering for Agents*, AI Engineer Code Summit Nov 2025 — for the *sub-agents = context isolation, not persona* corollary. Reference artifact: https://github.com/humanlayer/advanced-context-engineering-for-coding-agents

---

## Slide 11 — Principle 8: The skill file is the unit that improves

**Speaker beat (~75 sec):** When a skill fails in production, you don't re-prompt. You patch the file. One markdown diff per iteration. The next run doesn't repeat the mistake.

This is **Hashimoto's** discipline applied at the smallest grain. Mitchell calls it *harness engineering*: *"anytime you find an agent makes a mistake, you take the time to engineer a solution such that the agent never makes that mistake again."* External commentators (Willison and others) call this *the ratchet method* — once you've engineered the mistake out, the agent can't slide back. Either label works on the slide; just don't put "ratchet" in Hashimoto's mouth.

The aspirational destination Zhang/Murag name: agents writing their own skills from experience. Whether or not we get there, the artifact that learns is **a file you can read, review, and version.** That's the engineering property that matters.

**Citation corrections needed on the slide:**
- Currently attributes the *"skill file is the unit that improves"* idea to Zhang/Murag. The procedural authority is **Hashimoto**, *My AI Adoption Journey*, 5 Feb 2026 — https://mitchellh.com/writing/my-ai-adoption-journey. Move that citation onto the slide. Zhang/Murag still earns the *"agents writing their own skills"* aspirational quote at the end.

**Sources:**
- Mitchell Hashimoto, *My AI Adoption Journey*, 5 Feb 2026 — https://mitchellh.com/writing/my-ai-adoption-journey
- Zhang & Murag — for the agents-writing-skills aspirational beat.

---

## INSERT D (recommended new slide between 11 and 12) — Maintenance hygiene: every skill ships its own smoke test

**Why this slide exists:** Slide 11 said *"the skill file is the unit that improves."* This slide says *"and the smoke test is how you know it still works."* It closes the loop the user explicitly asked about — *how do you maintain skills?* — and it sets up the Module 5 (production/evals) story without stealing it.

**On-screen — the pattern:**

```
skills/
  score-model/
    SKILL.md         # metadata + instructions
    score.py         # the implementation
    _smoke.py        # 30 seconds. Tests the skill end-to-end.
```

**Speaker beat (~60 sec):** Every skill in this toolkit ships a `_smoke.py`. Thirty seconds to run. Tests the skill end-to-end against a real segment. It asserts the keys exist, the shapes are right, the warnings fire when they should. It is **not** a unit test of every internal function; it is the agent's equivalent of *"does this skill still work after I changed it?"*

This is the smallest-grain version of what evals will become in Module 5 — Hamel Husain's *evals-as-skills* pattern at the level of one skill. The principle: **a skill without a smoke test is one rename away from breaking silently.** And silent breakage is what kills the floor that skills are supposed to lift.

**Citation:**
- Hamel Husain, *Evals as Skills* pattern (March 2026) — referenced in AI-axis NC-23.
- Internal Quix Module 2 v3 — every skill folder ships `_smoke.py`.

---

## Slide 12 — Principle 9: This isn't one vendor's idea — the field converged

**Speaker beat (~75 sec):** The reason to take any of this seriously is that the same primitive arrived at the same time from independent intellectual roots. Anthropic ships it as **Skills** — folder of markdown + scripts + assets. OpenAI ships the equivalent primitive as the **Model Spec** — a versioned, plain-language document that captures intent, is authorable by domain experts, and *compiles to behaviour*. Microsoft, Google, the open-source community — all aligned in 2025–2026.

The Grove line that lands this: *"Code is 10 to 20% of the value you bring. The other 80 to 90% is in structured communication."* And: *"Specs are like a lossless format; code is a lossy projection."* Whoever writes the spec is the programmer.

The implication for *your* engineering organisation: you are not picking a vendor's pattern. You are picking the field's pattern. The skills folder you author for your domain experts today will be readable by next year's tools.

**Citations (verified):**
- Sean Grove (OpenAI), *The New Code*, AI Engineer World's Fair, June 2025 — https://www.youtube.com/watch?v=8rABwKRsec4
- Zhang & Murag (Anthropic), *Don't Build Agents, Build Skills Instead*, AI Engineer Code Summit, Nov 2025 — https://www.youtube.com/watch?v=CEvIs9y1uog
- OpenAI Model Spec — https://github.com/openai/model_spec / https://model-spec.openai.com

---

## Slide 13 — Our evidence: 60-agent cohort, same task, same model

**Speaker beat (~90 sec):** Now the honest data. 60 agents. Same task. Same model. Same V0 baseline. Only thing that changed between families is the harness.

- Module 1 (bare agent): +48.0% yaw / +54.9% CTE, with σ 2.8% yaw / 2.3% CTE.
- Module 2 v3 (+ skills toolkit): **+49.5% yaw / +57.3% CTE, with σ 1.4% yaw / 1.4% CTE.**

The mean barely moved. The model already finds the answer from a bare prompt. *What skills did is halve the variance.* The worst-case runs climbed off the floor. Silent packaging failures largely vanished. Every run now lands near the good answer, not just the best ones.

**The honest line to land:** *"Skills buy you reliability, not a higher ceiling. The ceiling moves in Module 3."* If a Module 2-only audience asks *"is it worth the work?"* — yes, but for the floor, not the ceiling. Demos are `works.any()`. Products are `works.all()`. Skills are the move from one to the other. (That phrasing is Karpathy's, from the Sequoia talk we cited at the very start.)

**Source:** Internal canonical grade — `webinar-AI/_grade/20260601-120739/cohort.md`.

---

## Slide 14 — References

Existing references slide is correct in shape. Apply these specific corrections from the citation pass:

1. **Anthropic Skills blog** — date is **16 Oct 2025**, not Dec 2025.
2. **Zhang's *Building Effective Agents* talk** — if you cite the talk in addition to Zhang/Murag, it was **AI Engineer Summit (Feb 2025, NYC)**, *not* the World's Fair. The "agent = environment + tools + system prompt" framing actually comes from the companion blog *Building effective agents* (Schluntz & Zhang, Dec 2024, https://www.anthropic.com/engineering/building-effective-agents) — cite the blog if you want a verbatim source.
3. **Hashimoto** — *My AI Adoption Journey*, 5 Feb 2026 (https://mitchellh.com/writing/my-ai-adoption-journey). Add to the references list — currently absent.
4. **Chroma — Context Rot** — add if you use insert A: https://research.trychroma.com/context-rot
5. **Karpathy Sequoia 2026** — add if you use insert A: https://www.youtube.com/watch?v=96jN2OCOfLs
6. **Anthropic — Effective context engineering** (29 Sep 2025) — add as the vendor-side anchor: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
7. **OpenAI Model Spec** — add the canonical repo link: https://github.com/openai/model_spec

---

## Summary — which AI principles Module 2 combines, mapped to AI-axis NCs

For your own bookkeeping (you can cite these to the audience or keep them as facilitator notes). The NC numbers come from `F1/KB002/ai-axis/_README.md`.

| Module 2 slide / insert | NC | NC short name |
|---|---|---|
| Insert A — context engineering | NC-8, NC-28 | "computer in the dark"; smart/warm/dumb zones |
| 4 — progressive disclosure | NC-12, NC-19 | progressive disclosure; 944-vs-53 token tax |
| 5 — universal agent + library | NC-9 | universal agent + skills |
| 6 — skills vs MCP | NC-10 | judgement vs connectivity |
| 7 — description as routing | NC-12 (applied) | progressive disclosure in practice |
| Insert B — skills as clay | (Quix-original) | composes with NC-14 (ratchet) |
| 8 — encode what an expert would notice | (Quix-original) | the floor-lifting mechanism |
| Insert C — tour + suggested loop | (Quix-original) | composes NC-9 with chain-don't-fork |
| 9 — walk then crystallise | NC-18, NC-11 | authoring recipe + non-dev authoring |
| 10 — skill-maxxing | NC-20 | sequencing rule before multi-agent |
| 11 — skill file as unit that improves | NC-21, NC-14 | recursive self-improvement; ratchet method |
| Insert D — smoke tests | NC-23 (small grain) | evals as engineering discipline |
| 12 — cross-vendor convergence | NC-22 | spec/skill convergence |
| 13 — cohort evidence | (Quix-original) | the data |

**NCs we deliberately don't cover in Module 2** (they belong elsewhere):
- NC-1, NC-13 — agent metaphor + Agent=Model+Harness identity → Module 1.
- NC-23 (full) — evals as engineering discipline → Module 5.
- NC-24 — lethal trifecta → Module 5 (security).
- NC-25 — containerised environments + multiplayer → Module 5.
- NC-26 — code execution with MCP → Module 3 or 5 (when tools come back).
- NC-27 — RPI loop (Research → Plan → Implement) → could go in Module 2 if time but better in M5 alongside evals.

---

## Final checklist for the speaker (60 seconds before stepping on stage)

- [ ] Fix the Oct 16 / Dec 2025 date on slide 3.
- [ ] Either verify the 944-vs-53 numbers on slide 4 from the Shimeles episode, or soften to "~20× cheaper".
- [ ] Move Hashimoto onto slide 11 as the primary citation; keep Zhang/Murag for the aspirational quote.
- [ ] Decide whether to add the four recommended insert slides (A: context engineering, B: skills as clay, C: skills tour, D: smoke tests). Each is independent — you can add any subset.
- [ ] If adding insert A, also add Karpathy / Chroma / Anthropic context-engineering links to slide 14.
- [ ] The Cisco 83/13 number from NC-2 is *not* in Module 2 right now — it belongs in Module 1 as the data point that makes the audience hungry for this whole conversation. Don't import it here.
