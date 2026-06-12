---
title: "Module 2 — Skills: outline + speaker notes"
audience: webinar — "AI for engineering" thesis
length-target: ~20 slides / ~25 minutes
spine: what-are-skills → how-to-write → how-to-maintain → the-ten-skills-here
positioning: Module 1 was the bare agent. Module 2 deepens the *harness* by adding a skills layer.
updated: 2026-06-03
---

# Module 2 — Skills

> **One-line thesis.** A *skill* is a folder of metadata + instructions + scripts that a frontier model loads on demand. It's how an organisation makes its expertise *loadable* — and it's the layer where the **floor rises and the worst run stops embarrassing you**.

> **What changed from Module 1 to Module 2 in the canonical 60-agent grade.**
> Yaw Δ%: +48.0% → +49.5%. CTE Δ%: +54.9% → +57.3%.
> Yaw σ: **2.8% → 1.4%**. *That's where the win is.* Skills bought reliability, not a bigger ceiling. (See `module-principles.md` for the table.)

---

## Section A — Framing (Slides 1–3)

### Slide 1 — Recap: where Module 1 left us

**Visual.** Module 1 architecture diagram: `Model + permissions + tools + task prompt → agentic IDE-style loop`. Below it, the canonical grade row for Module 1 (+48.0% yaw, +54.9% CTE, σ 2.8%).

**Speaker notes.**
In Module 1 we ran the bare agent — a capable frontier model with permissions, tools, data access, and a task prompt. That's it. We deliberately kept the harness minimal so we could see what a modern model does on its own.

The headline: the median agent already rediscovered the core physics of the problem from the prompt. Frontier models are genuinely good now — that's not the punchline, that's the *premise*. What that lets us argue honestly is that the remaining gains live in the harness, not in waiting for a bigger model.

The cost of running no harness was visible in two places. The **variance** — σ of 2.8% on yaw — meaning the worst agent in the cohort is far behind the best. And the **silent failures** — one agent shipped an import error; one platform got silently skipped because its column name didn't match. Module 2 is about engineering both of those out.

**Source.** Internal — canonical grade cohort, run `20260601-120739`, `webinar-AI/_grade/`.

---

### Slide 2 — The reframe: Agent = Model + Harness

**Visual.** Equation centred: **Agent = Model + Harness**. Underneath: the six harness components from BettaTech — *tools, memory/state, context, planning, verification, modularity*. Highlight the four Module 2 touches: tools, context, verification, modularity.

**Speaker notes.**
When an agent fails in production, the engineer's instinct is *"the model isn't smart enough yet."* The harness-engineering literature reframes that. The agent is the model plus everything around it: the tools you wire in, the state you keep, the context you curate, the plan it executes, the checks that catch its mistakes, and the way you've modularised all of the above.

Today's module deepens that harness in one specific way — we add a **skills** layer. Skills primarily touch four of those six components: they're a unit of *tools* (the scripts inside), of *context* (the metadata + instructions that get loaded on demand), of *verification* (a skill can carry signed-bias warnings or contract checks), and of *modularity* (one skill per workflow, composable).

**Source.** BettaTech, *¿Qué es esto del Harness Engineering?*, YouTube April / May 2026 (synthesising Hashimoto, Anthropic Engineering, Fowler, Osmani). Equation echoed by Rajiv Shah, *Harness Engineering* (2026); *From Prompts to Harnesses* (bits-bytes-nn, April 2026). **NC-13.**

---

### Slide 3 — "Don't build agents, build skills instead"

**Visual.** Two screenshots side by side: Zhang's *Building Effective Agents* talk title slide (mid-2025) ↔ Zhang & Murag's *Don't Build Agents, Build Skills Instead* title slide (late 2025). Caption: *Same speaker. Six months apart. The course-correction is the lesson.*

**Speaker notes.**
The most credible sign of where this field is heading is when the people who evangelised the earlier framing publicly course-correct. Barry Zhang at Anthropic delivered the canonical *Building Effective Agents* talk in mid-2025. Six months later he was back on stage with Mahesh Murag at the AI Engineer Code Summit with a title that reads like a retraction: *Don't Build Agents, Build Skills Instead*.

The new thesis: **one universal agent + a library of domain-specific skills** beats one bespoke agent per domain. The diagnosis is straightforward — agents are brilliant generalists that *lack expertise* and don't absorb your domain knowledge well. The prescription is to stop trying to grow expertise into the agent and instead *package* expertise as skills the agent can load.

This is what Module 2 is. The universal agent is the same one you saw in Module 1. The library is the ten skills sitting next to it. By the end of this module you'll know what they are, how to write them, how to maintain them, and you'll have seen one in detail.

**Sources.**
- Barry Zhang & Mahesh Murag, *Don't Build Agents, Build Skills Instead*, AI Engineer Code Summit (YouTube: `https://www.youtube.com/watch?v=CEvIs9y1uog`).
- Barry Zhang, *How We Build Effective Agents*, AI Engineer World's Fair 2025.
- **NC-9** (universal agent + library of skills — architectural backbone).

---

## Section B — What is a skill (Slides 4–7)

### Slide 4 — A skill, mechanically

**Visual.** A `skills/score-model/` folder tree:
```
skills/score-model/
├── SKILL.md          ← metadata + instructions (the contract)
├── score.py          ← the script the agent runs
├── _shared/          ← assets (helpers, schemas)
└── README.md         ← human notes
```

**Speaker notes.**
Mechanically a skill is just a folder. Inside it: one `SKILL.md` with metadata and instructions at the top, the scripts the agent executes, and any supporting assets — schemas, templates, reference data.

The critical thing is that there are two layers of content. There's the *metadata* — short, structured, sits in the frontmatter. And there's the *body* — the real procedural guidance, the script descriptions, the warnings. The metadata is read by the agent at startup. The body is loaded **only when the metadata says the skill is relevant to the current task**.

That two-layer structure is the entire technique. It's called *progressive disclosure*. The next slide unpacks why it matters.

**Sources.**
- Anthropic Engineering, *Equipping agents for the real world with Agent Skills* (Dec 2025): `https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills`.
- Claude Docs, *Agent Skills overview*: `https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview`.

---

### Slide 5 — Progressive disclosure: the 944-vs-53 number

**Visual.** Two bars side by side.
- Left bar — `AGENT.md` always loaded: **≈ 944 tokens / turn**.
- Right bar — equivalent skill metadata-only until invoked: **≈ 53 tokens / turn**.
- Caption underneath, large type: ***every. single. turn.***

**Speaker notes.**
Here's the economics. The same body of guidance, packaged two ways. Stuffed into an always-loaded `AGENT.md` file, you pay roughly 944 tokens every turn of the conversation — whether the agent needs that guidance on this turn or not. Packaged as a skill loaded by metadata, you pay roughly 53 tokens every turn — the metadata header — and you only pay the rest when the agent decides the skill is relevant.

The number is from Michael Shimeles, who walked through the anatomy of the context window on Greg Isenberg's *Startup Ideas Podcast* in April 2026. The exact number isn't the point — the *ratio* is. About 18×.

Now multiply that by twenty skills in your toolkit, by every turn of every agent run, by every developer on your team. The cost of *not* using progressive disclosure isn't just dollars — it's that you blow through your context window before the agent has had a chance to think.

**Sources.**
- Michael Shimeles (Ras Mic), *How AI Agents & Claude Skills Work*, Greg Isenberg's *Startup Ideas Podcast*, April 2026.
- Anthropic Engineering, *Effective context engineering for AI agents*: `https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents`.
- **NC-12** (progressive disclosure) + **NC-19** (the per-turn token tax).

---

### Slide 6 — Why progressive disclosure isn't optional: context rot

**Visual.** Empirical curve: x-axis = context fill %, y-axis = task success rate. Three labelled zones: **Smart (<30%)**, **Warm (30–40%)**, **Dumb (>40%)**. The 40% inflection marked with a dashed vertical line. Caption: *"You do not get to fill the context. You get 40% before things get bad."*

**Speaker notes.**
A frontier model has a 200k or even 1M token context window. It's tempting to treat that as a hard drive: pack everything in, let the model figure it out. That's wrong, and it's wrong empirically — not theoretically.

Chroma Research published a study called *Context Rot* in 2026 that measured degradation on a 200k-token model and found it starts to lose the plot around 50k tokens — well before the limit. Dex Horthy at HumanLayer, working on brownfield codebases, named the three observed zones: **smart** below about 30% fill, **warm** between 30 and 40%, and **dumb** above 40% — where measurable failure rates appear.

That 40% inflection is the working threshold. Anything you load that isn't earning its place is pushing the agent toward the dumb zone. Skills exist *because of* this curve — they let you have a large knowledge library and a small working context at the same time.

**Sources.**
- Chroma Research, *Context Rot: How Increasing Input Tokens Impacts LLM Performance* (2026): `https://www.trychroma.com/research/context-rot`.
- Dex Horthy (HumanLayer), *Advanced Context Engineering for Agents*, Context Engineering SF late 2025 / *No Vibes Allowed*, AI Engineer Code Summit Nov 2025.
- **NC-8** (computer in the dark) + **NC-28** (smart/warm/dumb zones).

---

### Slide 7 — Skills vs MCP: judgement vs connectivity

**Visual.** Two columns.
- **MCP server** — *"How do I reach the system?"* — ERP connector, telemetry store, Quix topic, ticketing API.
- **Skill** — *"What do I do once I'm there?"* — three-way-match invoice, diagnose lateral-fidelity residual, prepare deliverable for shipping.
- Bottom: *"Most real workflows need both."*

**Speaker notes.**
The other artifact engineers reach for right now is MCP — the Model Context Protocol. Both are good. They solve different problems.

MCP servers are *connectivity*. They let an agent reach a system it couldn't otherwise see — an ERP, a database, a calendar, a Quix topic. They're universal external connectors.

Skills are *judgement*. They're the procedural knowledge for what to do once you've reached the system. Business rules, workflows, the order in which to do things, the warning to display, the output format.

The clean mental hook from Zhang and Murag: when you hit a new workflow, ask whether the gap is *connectivity* or *judgement* before reaching for either tool. The accounts-payable example they use is an ERP MCP server giving the agent access to invoices, plus a *three-way-matching* skill that contains the procedural recipe.

For an F1 telemetry agent the same pairing holds. The telemetry store is reached via an MCP server. The procedure for diagnosing a lateral-fidelity residual — what to score first, when to look at bias before noise — is a skill.

Both are good. Most real workflows need both.

**Sources.**
- Zhang & Murag, *Don't Build Agents, Build Skills Instead* (above).
- Simon Willison, *Pelicans on Bicycles*, AI Engineer World's Fair June 2025 (Best Speaker) — non-vendor anchor on MCP: *"tools + reasoning is the most powerful technique in AI engineering right now."*
- **NC-10**.

---

## Section C — How to write skills (Slides 8–12)

### Slide 8 — The recipe: walk → crystallise → iterate

**Visual.** Three-step arrow with rough effort distribution:
1. **Walk the workflow manually.** Drive the agent yourself; correct in real time. *(~60% of effort.)*
2. **Crystallise.** After one clean end-to-end run, ask the agent to write the run into a `SKILL.md`. *(~10%.)*
3. **Iterate against failure.** Run the skill on new cases; when it fails, feed the failure back and have the agent patch the skill. *(~30%, ~5 iterations.)*

**Speaker notes.**
The reliable recipe for writing a skill that actually works has three steps. Most of the work is in step one and most of the polish is in step three.

Step one: walk the agent through the workflow you want to automate, with you driving and correcting in real time. You're not writing a skill yet — you're doing the task with the agent's help, the way a senior would supervise a junior. The point of this step is to *find out what the recipe actually is*. Most workflows engineers think they understand turn out to have edge cases they only notice when the agent gets them wrong.

Step two — only after one clean end-to-end run — is to crystallise. Ask the agent to turn the run into a `SKILL.md`. It will do a good first draft. Don't ship that draft.

Step three is iteration. Run the skill on five or ten new cases. When it fails, feed the failure back and have the agent patch its own skill file. About five iterations gets you to production-reliable for most workflows.

Notice who's in the critical path. Steps one and two — a domain expert can do them. An AI engineer isn't necessarily needed. That's the democratisation move we'll come back to at the end.

**Sources.**
- Michael Shimeles (Ras Mic) — *walk-the-workflow* methodology, *Startup Ideas Podcast*, April 2026.
- **NC-18** (walk-the-workflow-first) + **NC-11** (non-developers authoring).

---

### Slide 9 — Write metadata for *routing*, not for *description*

**Visual.** Side-by-side `SKILL.md` headers.

**Bad.**
```yaml
description: A skill that scores models.
```

**Good (`scoring-model` from this project).**
```yaml
description: Score any predict callable against segment sim.csv files
  and return a rich diagnostic bundle — pooled yaw-rate RMSE and CTE
  RMSE; per-segment table; per-platform residual stats; signed-bias
  warnings. Schema-aware. Use as the inner-loop oracle.
when-to-invoke: You have a model and want a complete view of how it
  performs — not just KPIs but which segments dominate the error.
when-NOT-to-invoke: You only need raw segment data (use
  loading-segments); you want to compare two models head-to-head
  (use compare-models); you want to optimise coefficients (use
  fitting-model).
load-cost: ~200 tokens metadata, ~520 tokens body.
```

**Speaker notes.**
The metadata's job is not to *describe* the skill — it's to help the agent *choose correctly under progressive disclosure*. That sounds subtle. It's the single biggest mistake people make.

If your description says "a skill that scores models," the agent has to guess whether your task calls for it. If it says what *signal* the skill produces, when to invoke it, and — critically — when *not* to invoke it pointing at the correct sibling, the agent doesn't guess. It routes.

The `when-NOT-to-invoke` field is unusual and it's the part that does the work. Notice ours actively redirects: *"you want to compare two models head-to-head, use `compare-models`."* The agent reads that and saves a wrong turn.

This is the lesson the v1-to-v3 tuning of this template taught us. Same skills, same code — sharper metadata. That alone dropped variance across the cohort from σ 2.8% to σ 1.4%. The agent finding the right skill *first* is what bought the reliability.

**Sources.**
- Anthropic Skills documentation, *SKILL.md schema*.
- Internal — `module-2.v3/agent-01/skills/score-model/SKILL.md`.
- Empirical — Module-2 v1 vs v3 cohort grade (`module-principles.md`, Principle 6).

---

### Slide 10 — Skills carry **judgement**, not just mechanics

**Visual.** Snippet of `score-model`'s output summary header:

```
🚨 BIAS WARNINGS
  FORD_F_150_LIGHTNING_MK1 — yaw signed bias 0.012 rad/s (>0.008 threshold)
  TESLA_MODEL_3            — CTE signed drift 4.7 m (>3.0 threshold)

CTE is a double-integral of yaw error. A non-zero signed bias is what
kills CTE-RMSE, not the per-sample noise floor. Look at this BEFORE
you ship.
```

**Speaker notes.**
This is the slide I'd put on a fridge. A skill is not a wrapper around a function call. A skill is *what an expert would notice*, encoded.

Compare two implementations of `score-model`. Version A returns the numbers — yaw RMSE, CTE RMSE, done. Version B is what we ship: it returns the numbers *and* opens with a signed-bias warning block, *and* tells the agent in plain text why that block matters — CTE is a double-integral of yaw error, so a small signed bias dominates CTE-RMSE regardless of how clean the per-sample noise looks.

Why does that matter? Because the optimiser cannot see this. The fit converged. The number looked fine. An engineer who'd done this task before would glance at the per-platform bias and immediately know what's wrong. The skill encodes that glance.

`fit-model` does the same thing — it opens with warnings the optimiser cannot see itself: co-collapse, overfit, stuck-on-bound. `residual-structure` doesn't return a metric, it returns a *verdict* — `noise_floor` (you're done) or `structure_detected` (here's the term to add). Those are the skills that move the floor up.

This is also the line that earns trust with senior engineers. A skill that just runs a script isn't worth the abstraction. A skill that names the *thing only an expert would have known to look for* — that's the artifact your organisation's expertise lives in.

**Sources.**
- Internal — `score-model/score.py`, `fit-model/fit.py`, `residual-structure/structure.py`.
- Conceptual lineage — Hamel Husain, *Evals as Skills* pattern (March 2026); Anthropic Skills docs.

---

### Slide 11 — Skills are designed to **chain**, not fork

**Visual.** A flow diagram of the suggested loop from `module-2.v3/AGENTS.md`:

```
score → (read bias check) → fit → diagnose residual → re-score
                                       │
                                       ├── noise_floor? → ship
                                       └── structure_detected? → add term → refit
```

**Speaker notes.**
A common failure mode of skills toolkits is that they end up as ten independent buttons. The agent learns each one in isolation, then sits there at the top of the task wondering which button to press.

Good skills tell you what to do *next*. Our `score-model` doesn't just return numbers — its `when-NOT-to-invoke` actively redirects to `compare-models` or `fitting-model`. Its summary tells the agent that if the bias warning fires, the next step is `fit-model` with bounds — not another scoring run. `residual-structure` returns a verdict whose `structure_detected` reason names the specific term to add.

The toolkit ships a suggested loop in `AGENTS.md`: score → bias check → fit → diagnose → re-score. The skills compose into a workflow rather than presenting a flat menu. That's not an architectural choice you can defer — it's how you decide what *shape* the skills should have in the first place.

The rule of thumb: when you finish writing a skill, ask *"after the agent invokes this, what does it do next?"* If the answer isn't already encoded somewhere, the skill isn't finished.

**Sources.**
- Internal — `webinar-AI/webinar-meta/webinar-00-template-m2.v3/AGENTS.md`, *Suggested loop* section.
- Anthropic, *Building Effective Agents* (workflow-vs-agent distinction).

---

### Slide 12 — Zoomed example: anatomy of `score-model`

**Visual.** Annotated full `SKILL.md` for `score-model` on a single slide. Three callouts:
1. **The frontmatter** — metadata that does routing (description / when-to-invoke / when-NOT-to-invoke / load-cost).
2. **The judgement** — signed-bias warning block surfaced at the top of the summary, with the *why* in plain text.
3. **The contract** — the fixed `predict_fn(sim_df, platform) → DataFrame` signature that lets every other skill in the toolkit interoperate.

**Speaker notes.**
This is the only skill we'll look at line by line. Pick this one because it's the inner-loop oracle — every other skill in the toolkit either feeds it or consumes from it.

Three things to notice.

First, look at the frontmatter. The description doesn't describe — it tells the agent *what signals* the skill produces and *when to reach for it*. The `when-NOT-to-invoke` actively pushes the agent to the right sibling. The `load-cost` line — 200 tokens for metadata, 520 for the body — is the budget the agent uses when deciding what to load. This is progressive disclosure operationalised at the per-skill grain.

Second, the judgement is at the top, not at the bottom. The bias-warning block is the first thing `format_summary()` prints. The text explains *why* it matters — CTE is a double integral of yaw error — in language the agent can quote in its own reasoning. We're not asking the agent to be the expert. We're handing it the expert's first glance.

Third, the contract. Every skill in this toolkit conforms to one tiny convention: `predict_fn(sim_df, platform) → DataFrame with yaw_rate_pred_rads column`. That's why `score-model` and `compare-models` and `fit-model` can be chained — they all agree on what the agent's model looks like. *Composability is contract.* If you skip this when designing your toolkit, you'll end up with ten skills that can't talk to each other.

**Sources.**
- Internal — `module-2.v3/agent-01/skills/score-model/SKILL.md`.

---

## Section D — How to maintain skills (Slides 13–15)

### Slide 13 — Skill files are the unit of recursive self-improvement

**Visual.** Markdown diff before/after — three iterations of one `SKILL.md`. Highlighted: a new `when-NOT-to-invoke` line, a sharpened warning threshold, a new warning the agent learned from a real failure case.

**Speaker notes.**
A skill isn't a one-shot artifact. It learns. The mechanism is simple and tangible: when the skill fails on a new case, feed the failure back to the agent and ask it to patch its own `SKILL.md`. After roughly five iterations you have something production-reliable.

The reason this is satisfying as a teaching moment is that the artifact that's improving is a *markdown file*. You can diff it. You can review the change in a PR. You can roll it back. The recursive self-improvement loop everyone gestures at — the agent that gets better over time — turns out, at the artifact grain, to be a markdown file getting slightly better every Tuesday.

Three of our `SKILL.md` files have iteration history visible in the v1→v3 evolution of this template. None of the *code* changed. The metadata sharpened, the warnings got more specific, the cross-references between skills got more aggressive. That's what dropped cohort variance from σ 2.8% to σ 1.4%.

**Sources.**
- Michael Shimeles (Ras Mic), *Startup Ideas Podcast*, April 2026 — *skill files as the unit of recursive self-improvement*.
- Conceptual lineage — Cassie Kozyrkov (ex-Google), *How to Customize Agentic AI for Your Organization*, LinkedIn Live 2025 — *self-improving harness*.
- **NC-21** + **NC-3**.

---

### Slide 14 — The ratchet method: engineer out every mistake structurally

**Visual.** Two columns labelled *Wrong* and *Right*, with one example below each.

- **Wrong** — Agent scored Tesla with the wrong column name; output was silently empty. *Fix: re-prompt with "make sure you handle Tesla."*
- **Right** — Add `PLATFORM_SCHEMA` mapping to `score-model`. The bug is now structurally impossible. Same fix applies on every future run. *Diff visible in the v1→v3 history.*

**Speaker notes.**
This is Mitchell Hashimoto's term, by way of BettaTech: the *ratchet method*. Every agent mistake gets engineered out **structurally** — in `AGENTS.md`, in a linter rule, in a tool wrapper, in a skill warning — never re-prompted away.

The temptation when an agent makes a mistake is to add the correction to your next prompt. *"This time, make sure you handle the Tesla schema."* That fixes the symptom on the next run. It does not stop the next agent from making the same mistake.

The ratchet version: open the relevant skill, add the structural fix — in our case a `PLATFORM_SCHEMA` mapping that resolves the right column per platform. Now the bug is *gone*. The next run, the run after, the run six months from now when somebody adds a new platform — they all benefit. Failures become inputs to the next iteration.

This is also why `AGENTS.md` should be read as *"the changelog of every mistake your agents have made, written in the imperative."* Same applies to skills. Every warning in a `SKILL.md` is a hard-won lesson sitting there waiting to save the next agent five hours.

**Sources.**
- Mitchell Hashimoto, *My AI Adoption Journey* (Feb 2026).
- BettaTech, *¿Qué es esto del Harness Engineering?*, YouTube April / May 2026.
- **NC-14**.

---

### Slide 15 — Guides vs sensors: feedforward and feedback in the same toolkit

**Visual.** Two columns.

- **Guides (feedforward)** — *prevent* the wrong behaviour before it happens.
  - `SKILL.md` metadata that routes the agent to the right skill.
  - `when-NOT-to-invoke` lines.
  - The `predict_fn` contract.
- **Sensors (feedback)** — *detect* the wrong behaviour after it happens.
  - `score-model` signed-bias warnings.
  - `fit-model` co-collapse / overfit / stuck-on-bound warnings.
  - `pre-flight-final-model` contract checker.
- Caption: *Computational sensors first (deterministic, fast). Inferential sensors only where they earn it.*

**Speaker notes.**
A useful vocabulary from outside the AI world — Birgitta Böckeler and Martin Fowler, via BettaTech. Every harness component is either a *guide* or a *sensor*. Guides are feedforward control — they tell the agent what to do before it acts. Sensors are feedback control — they catch what the agent did wrong after the fact.

Both your skills toolkit is doing both. The metadata is a guide — it routes the agent to the right skill at the right time. The bias-warning block in `score-model`'s output is a sensor — it watches what the fit produced. The `pre-flight-final-model` skill is a sensor that enforces the deliverable contract.

The diagnostic question this gives you, whenever something goes wrong: *missing guide, or missing sensor?* If the agent took the wrong path, the guide is missing or weak. If the agent took the right path but produced something that should have raised an alarm, the sensor is missing.

One sub-distinction worth keeping in mind: computational sensors — `pre-flight-final-model`'s contract check, a linter, a type-checker — are deterministic and fast. Run those first and often. Inferential sensors — asking another LLM to judge — are expensive. Reserve them for what only a model can judge. Most production harnesses get this budget wrong.

**Sources.**
- Birgitta Böckeler / Martin Fowler — *control-systems vocabulary for AI harnesses* (via BettaTech, April / May 2026).
- **NC-15**.

---

## Section E — The ten skills in this project (Slides 16–17)

### Slide 16 — Toolkit inventory

**Visual.** Table — one row per skill — three columns: *Skill / What it does / What kind*.

| Skill | One-line value | Role |
|---|---|---|
| `score-model` | Inner-loop oracle. Pooled yaw + CTE, per-segment table, per-platform residual stats, **signed-bias warnings at the top**. Schema-aware. | Sensor + judgement |
| `fit-model` | Optimise per-platform coefficients of any opaque model via scipy. Opens with **fit warnings** (co-collapse / overfit / stuck-on-bound) and shows the **train/dev gap inline**. | Mechanics + sensor |
| `residual-structure` | After a fit, characterises what's LEFT in the residual: autocorrelation, feature correlations, sign-asymmetry. Returns a **verdict** — `noise_floor` (you're done) or `structure_detected` (here's the term to add). | Bridge / judgement |
| `route-bias` | Group residuals by `(platform, route)`; rank routes by share of platform's pooled error; surface input-feature correlations to find the variable to add to the model. | Diagnostic |
| `compare-models` | Diff two `predict()` functions per-segment. Surfaces top regressions and top improvements. | Diff oracle |
| `inspect-residuals` | 1-D scatter or 2-D heatmap of yaw residual vs input features. Schema-aware. | Visualisation |
| `visualise-segment` | Render a multi-panel PNG of one segment with truth + predictions overlaid. | Visualisation |
| `make-train-dev-split` | Route-grouped train/dev split with a leakage validator. | Discipline |
| `load-segments` | Load segment `sim.csv` files with consistent dtype hygiene. | Connectivity |
| `pre-flight-final-model` | Verify the `final-model/` bundle matches the deliverable contract. | Sensor (contract) |

**Speaker notes.**
Ten skills. Each has a clear role in the loop. Five categories worth naming.

There's the *inner-loop oracle* — `score-model`. Called constantly; carries judgement at the top of its output.

There's the *mechanics-plus-sensor pattern* — `fit-model` runs the optimisation and *also* watches for the optimiser failing silently. The fit warnings on top are not decoration; they catch co-collapse, overfit, and stuck-on-bound — three things the optimiser cannot tell you have happened by reading the loss alone.

There's the *bridge skill* — `residual-structure`. The single most interesting one in the toolkit. It bridges *"I fit a model"* and *"should I build a better one?"* by examining the structure of what's left in the residual. Without this skill, the cohort ships V1 and stops. With it, the agent gets a verdict that explicitly tells it what term is missing.

There are *diagnostics and visualisations* — `route-bias`, `inspect-residuals`, `visualise-segment` — that the agent reaches for when it suspects a specific failure mode.

And there are *discipline and contract enforcers* — `make-train-dev-split` (route-leakage validator), `pre-flight-final-model` (deliverable contract). Both are sensors. Both engineer out a class of mistake structurally.

Notice what the toolkit does *not* contain. No "do the whole task" mega-skill. No "make-decisions-for-me" planner. Each skill is small, named for one job, and composes with the others through a shared `predict_fn` contract.

**Source.** Internal — `module-2.v3/AGENTS.md`, *Skills inventory*.

---

### Slide 17 — What the toolkit actually bought (cohort evidence)

**Visual.** Two charts side by side from the canonical grade.

- **Left** — mean improvement, Module 1 vs Module 2.v3. Bars look almost the same (+48.0% vs +49.5% yaw; +54.9% vs +57.3% CTE).
- **Right** — standard deviation. Bars look very different (yaw σ **2.8% → 1.4%**).

Caption underneath: *"Skills bought reliability, not a higher ceiling. The worst agent climbed off the floor."*

**Speaker notes.**
This is the honest version of the pitch.

The naive story is *"each layer of harness adds a few more points to the average."* That's not what the data says. The Module 2 mean barely moves above Module 1.

What *did* move is the variance. Yaw standard deviation halved. The worst agent in the cohort — the one that used to silently skip a platform, or ship an import error — climbed off the floor. Every run started landing the basics right. The deliverable contract was met every time. The signed-bias check stopped CTE from being killed by a fixable offset.

That's a real and sellable benefit. It's the difference between a demo where *some* of your runs work, and a product where *all* of your runs work. Andrej Karpathy frames it as `works.any()` versus `works.all()`. Skills are how you move from the first to the second.

The other thing this slide says, that we'll spend the next module unpacking — skills don't, by themselves, raise the *ceiling*. The cohort still topped out around the same place Module 1 did. The skills made the bottom climb up to meet the top. To move the ceiling, you need the layer Module 3 adds: domain knowledge that names the *non-obvious* winning move. That's the next module.

**Source.** Internal — canonical grade cohort, run `20260601-120739`, `webinar-AI/_grade/`; `module-principles.md` Section *The honest headline*.

---

## Section F — What we've actually been teaching (Slides 18–20)

### Slide 18 — The principles map

**Visual.** Two-column table — *principle / what it looked like in this module*.

| Principle | In Module 2 |
|---|---|
| Context engineering — the context window is the program | Progressive disclosure, the 944-vs-53 tax, the smart/warm/dumb curve |
| Compositionality — design for chains, not menus | `predict_fn` contract; suggested loop; cross-references in `when-NOT-to-invoke` |
| Encoded judgement, not raw mechanics | Bias warnings on top; fit warnings; verdicts not just metrics |
| Recursive self-improvement at artifact grain | `SKILL.md` files patched after each failure; the v1→v3 diff |
| Engineering-out mistakes structurally (the ratchet) | `PLATFORM_SCHEMA`; `pre-flight-final-model`; cross-route leakage validator |
| Skills vs MCP — judgement vs connectivity | The toolkit is all judgement; data access is the symlinked `data/` (Module 1 substrate) |
| Democratised authoring — domain experts write skills | Walk-the-workflow recipe; markdown + scripts, not bespoke agent code |
| One universal agent + many skills > N bespoke agents | Same agent, same model, same `AGENTS.md` — the toolkit is what changed |

**Speaker notes.**
Walk this table left-to-right and notice that everything on the left is a vendor-neutral principle and everything on the right is a concrete artefact you've just seen.

Context engineering is the umbrella term that's replaced "prompt engineering" in 2026. The reason is exactly this layer of work — most of the leverage isn't in the system prompt; it's in *what gets loaded into context at what moment*. Karpathy's line — *"the context window is the program"* — landed across both Anthropic and OpenAI camps.

Compositionality is software engineering's oldest principle, applied here. Skills compose; designing for that is the contract work.

Encoded judgement vs raw mechanics is the line between a tool that wraps a function and a skill that codifies what an expert would notice. That distinction is what moves the floor up.

Recursive self-improvement is the part everybody handwaves; at the artifact grain it turns out to be a markdown file getting better on Tuesdays.

Structural engineering-out — the ratchet — is the discipline that compounds over time.

Skills vs MCP keeps you from over-using either.

Democratised authoring is the workshop hook we'll come back to in the closing.

And the universal-agent-plus-skills shape is the architectural backbone the rest of the curriculum builds on.

**Sources.** Composite — see Sources slide.

---

### Slide 19 — Vendor-neutral: this is now the field's consensus

**Visual.** Two screenshots side by side.
- Left — Anthropic's `SKILL.md` example from `claude.com/docs`.
- Right — OpenAI's *Model Spec* on GitHub.
- Caption: *Same primitive. Independent intellectual roots.*

**Speaker notes.**
One reason to teach this layer with confidence: it's no longer Anthropic's pattern we're teaching. It's the field's.

Sean Grove gave a talk at AI Engineer World's Fair 2025 called *The New Code* on behalf of OpenAI's alignment team. His thesis: *"code is a lossy projection of intent; the specification is the lossless source."* OpenAI ships that as the *Model Spec* — versioned, clause-addressable markdown that compiles to documentation, evaluations, model behaviour, and prompts.

Anthropic ships the same primitive as Skills. Same shape — versioned, clause-addressable markdown, authorable by domain experts, compiles to behaviour. Microsoft, Google, and the open-source community have aligned on the pattern through 2026. The May 2026 cross-vendor consensus surveys triangulate this from independent practitioner blogs, audio sources, and vendor blogs — same finding from all three directions.

Practical implication for the audience: when you invest in writing skills, you're not betting on one vendor's API. You're investing in the artifact that the field has converged on.

**Sources.**
- Sean Grove, *The New Code*, AI Engineer World's Fair June 2025.
- Anthropic Engineering, *Equipping agents for the real world with Agent Skills* (Dec 2025).
- Cross-vendor 2026 consensus — `F1/KB002/ai-axis/resources/consensus-2026-*.md`.
- **NC-22**.

---

### Slide 20 — One last frame: the harness is the moat

**Visual.** Two lines, large type.

> *"The differentiator is the context and harness you build around the model."* — Ras Mic, 2026
>
> *"Demo is `works.any()`. Product is `works.all()`."* — Karpathy, 2026

**Speaker notes.**
The frontier models will keep getting better. Three months from now there'll be a smarter one. Six months from now there'll be a smarter one again. That's not the thing you should be planning your engineering team's quarter around.

What *you* own is the skills library. The metadata that routes the right one. The warnings that catch the optimiser's blind spots. The contract that lets your toolkit compose. The five iterations of failure you fed back into each `SKILL.md` last month. None of that came in the model's weights. All of it stays when you upgrade the model.

That's the move the audience should walk out with. The model is the commodity. The harness — and inside the harness, the skills library — is the moat. Module 3 is going to add the next layer of that moat: the hard-won domain judgement the people in your organisation paid for in scar tissue. But Module 2 is the layer that made everything reproducible enough to trust in the first place.

**Sources.**
- Michael Shimeles (Ras Mic), *Startup Ideas Podcast*, April 2026.
- Andrej Karpathy, Sequoia 2026 (verify exact wording before quoting publicly).
- Simon Willison, *Pelicans on Bicycles*, AIEWF June 2025.

---

## Appendix — Source pack (the "References" slide / handout)

**Anthropic (primary, vendor)**
- Anthropic Engineering — *Equipping agents for the real world with Agent Skills* (Dec 2025): `https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills`
- Anthropic Engineering — *Effective context engineering for AI agents*: `https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents`
- Claude Docs — *Agent Skills overview*: `https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview`
- Barry Zhang & Mahesh Murag — *Don't Build Agents, Build Skills Instead*, AI Engineer Code Summit: `https://www.youtube.com/watch?v=CEvIs9y1uog`
- Barry Zhang — *How We Build Effective Agents*, AI Engineer World's Fair 2025

**Cross-vendor / non-vendor**
- Sean Grove (OpenAI) — *The New Code*, AI Engineer World's Fair June 2025
- Simon Willison — *Pelicans on Bicycles*, AIEWF June 2025 (Best Speaker)
- Dex Horthy (HumanLayer) — *Advanced Context Engineering for Agents* / *No Vibes Allowed*, Context Engineering SF + AI Engineer Code Summit late 2025

**Practitioners**
- Michael Shimeles (Ras Mic) — *How AI Agents & Claude Skills Work*, on Greg Isenberg's *Startup Ideas Podcast*, April 2026
- BettaTech / Martín — *¿Qué es esto del Harness Engineering?*, YouTube April / May 2026 (Spanish)
- Mitchell Hashimoto — *My AI Adoption Journey* (Feb 2026)
- Cassie Kozyrkov — *How to Customize Agentic AI for Your Organization*, LinkedIn Live 2025
- Hamel Husain — *Evals as Skills* (March 2026)

**Empirical / research**
- Chroma Research — *Context Rot: How Increasing Input Tokens Impacts LLM Performance* (2026): `https://www.trychroma.com/research/context-rot`
- Rajiv Shah — *Harness Engineering: Why the System Around the Model Decides Agent Performance* (2026)
- *From Prompts to Harnesses — Four Years of AI Agentic Patterns* (bits-bytes-nn, April 2026)
- Hugging Face — *Harness, Scaffold, and the AI Agent Terms Worth Getting Right* (2026)

**Internal**
- Canonical grade cohort, run `20260601-120739` — `webinar-AI/_grade/`
- AI-axis NC framework — `F1/KB002/ai-axis/_README.md`
- Module-2.v3 harness — `webinar-AI/module-2.v3/`
- Module-principles synthesis — `webinar-AI/webinar-meta/module-principles.md`

---

## NC coverage map (for your own QA — not on a slide)

**Core hits this module embodies**
- **NC-9** — one universal agent + library of skills (architectural backbone) — Slide 3
- **NC-12** — progressive disclosure / metadata-first loading — Slides 5, 9, 12
- **NC-18** — walk-the-workflow-first methodology — Slide 8
- **NC-19** — the 944-vs-53 per-turn token tax — Slide 5
- **NC-10** — skills vs MCP — Slide 7
- **NC-21** — skill files as the unit of recursive self-improvement — Slide 13
- **NC-11** — non-developers authoring high-value skills — Slide 8 (and closing CTA in later module)
- **NC-22** — cross-vendor spec / skill convergence — Slide 19

**Strong supporting touches**
- **NC-7** — minimal agent definition (env + tools + system prompt) populated dynamically by skills — Slide 4
- **NC-14** — ratchet method applied to `SKILL.md` files — Slide 14
- **NC-13** — Agent = Model + Harness — Slide 2
- **NC-15** — guides vs sensors — Slide 15
- **NC-6** — workflow → universal-agent-with-skills → bespoke-agent decision tree — implicit in Slide 3

**Adjacent (one-liner each, deepened in other modules)**
- **NC-8** / **NC-28** — context engineering motivation (smart/warm/dumb curve) — Slide 6
- **NC-3** — self-improving harness (NC-21 is the artifact-grained version) — Slide 13
- **NC-16** — `AGENTS.md` as the cross-cutting sibling artifact — implicit in Slide 4
- **NC-4** — tokenmaxing antidote (progressive disclosure *is* this at the skills grain) — implicit in Slide 5
- **NC-20** — skill-maxxing sequencing rule (don't reach for sub-agents until skills are reliable) — kept for the closing module

---
