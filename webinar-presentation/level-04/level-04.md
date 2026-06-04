# Level 04 — Harness

---

## Slide 1 — Section opener

**04**

**LEVEL 04**

**HARNESS**

---

## Slide 2 — Definition

**Harness** *(noun)*

A harness is everything around the model that decides what it can see, what it can do, and when it is done. It is the file the agent loads first, the phase boundaries that decide which context comes next, the skills and references it can reach for, the guides that prevent wrong moves, the sensors that catch them, and the artifacts that record what was learned. Same model + better harness = different system.

*Source: synthesis of Mitchell Hashimoto (HashiCorp), Birgitta Böckeler & Martin Fowler (Thoughtworks), and the Anthropic Engineering blog — popularised under the name "harness engineering" by BettaTech, *¿Qué es esto del Harness Engineering?*, April 2026 — https://www.youtube.com/watch?v=Ah54fKwLn-Y*

---

## Slide 3 — The harness, built up

Animated diagram. Each frame adds one element to the previous frame. The starting frame is the final state of Level 02's skills shelf, so the audience watches the harness *grow around the loop they already know* rather than seeing a new picture.

**Frame 1 — The Level 02 picture, in grey.**
The completed Level 02 diagram fades in, rendered in greyscale: **Human ↔ LLM Call ← System Prompt ← skills/ metadata; LLM Call → tools → Environment → Feedback → LLM Call → Stop.** *Caption (optional):* "where we left off — one agent + a skills shelf."

**Frame 2 — `AGENTS.md` appears.**
A single markdown file materialises above the **System Prompt** container and feeds into it: **AGENTS.md** — the root index the agent reads on every session. Drawn deliberately small. *Caption (optional):* "the file every turn pays for — keep it cheap."

**Frame 3 — `phases/` appears around the loop.**
A larger container labelled **phases/** wraps everything to the right of the LLM Call. Inside it, three boxes appear left-to-right: **1-research**, **2-plan**, **3-implement**. *Caption (optional):* "the loop isn't one window any more — it's three."

**Frame 4 — Each phase produces a locked artifact.**
Inside each phase box, an output document appears: **RESEARCH.md → PLAN.md → final-model/**. Small padlock icons appear on RESEARCH.md and PLAN.md after their phase ends. Arrows between the phases are dashed and short — they are *file handoffs*, not conversation history. *Caption (optional):* "fresh context window per phase. The artifact is the connective tissue."

**Frame 5 — `references/` appears beside `skills/`.**
A second folder materialises next to the existing **skills/** folder: **references/** — `m4-cohort-findings.md`, `anti-patterns.md`, `f150-yaw-ceiling.md`. Dashed lines fan from the references into the **System Prompt** container, the same way skill metadata did in Level 02. *Caption (optional):* "what the cohort already learned, ratcheted into the harness."

**Frame 6 — Guides and sensors light up the boundary.**
Two new labels appear on the outer edges of the harness, in two different colours:
- **Guides** (feedforward) — a chip on `AGENTS.md`, on each phase boundary, on `lock.sh`. They *prevent* wrong moves.
- **Sensors** (feedback) — a chip on `score-model`, `pre-flight-final-model`, `critique-residuals`. They *detect* wrong moves.

*Caption (optional):* "every harness component is one or the other. A good harness has both."

**Frame 7 — Registries appear at the root.**
Three small files appear at the bottom of the harness, shared across phases: **MODELS.md / TREE.json / EXPERIMENTS.md** — the registry the agent appends to every iteration. *Caption (optional):* "the harness keeps memory the model can't."

**Frame 8 — Optional multiplayer.**
A faint dotted box appears around **3-implement**: **launch-rungs/** — N parallel subagents, same harness, different candidate branches, merge the winner. Drawn faded to signal *optional, only after skills are reliable.* *Caption (optional):* "subagents buy you fresh context, not personas."

### Final state — matches the dictionary entry on slide 2

The fully assembled diagram is the picture of slide 2's words:
- **AGENTS.md** — the file the agent loads first.
- **phases/** — the boundaries that decide which context comes next.
- **skills/ + references/** — what the agent can reach for.
- **guides** (chips) — prevent wrong moves.
- **sensors** (chips) — catch wrong moves.
- **MODELS.md / TREE.json / EXPERIMENTS.md** — the artifacts that record what was learned.

The Level 02 loop is preserved unchanged underneath; nothing about the agent or the skills shelf had to be replaced to add the harness. Harness is the *outer ring.*

*Source: anatomy borrowed from BettaTech's six-component synthesis (tools / memory-state / context / planning / verification / modularity) and Horthy's RPI loop. Composite picture, not a single talk's diagram.*

---

## Slide 4 — References (carousel)

Carousel of six cards. Each card: thumbnail + title + author/venue + 2–3 takeaway bullets.

### Card 1 — *Agent = Model + Harness* (the foundational identity)

**Author / venue.** BettaTech / Martín — *¿Qué es esto del Harness Engineering?* (Spanish-language synthesis of Hashimoto, Anthropic Engineering, Fowler, Osmani).
**Link.** https://www.youtube.com/watch?v=Ah54fKwLn-Y
**Thumbnail.** [level-04/bettatech-harness.jpg](level-04/bettatech-harness.jpg) *(to be added)*
**Takeaways.**
- The cultural reframe: when someone says *"my agent failed"*, the answer is *"no — your harness isn't finished yet."* Every component you add is one of six — tools, memory, context, planning, verification, modularity.
- The technical version of "the lamp is the point." The model is a commodity; the harness is where the engineering lives.

---

### Card 2 — *AGENTS.md as the artifact you actually ship*

**Author / venue.** Mitchell Hashimoto (HashiCorp founder) — *My AI Adoption Journey*, mitchellh.com, February 2026. Reinforced by Anthropic Engineering — *Equipping Agents for the Real World with Agent Skills*, December 2025.
**Link.** https://mitchellh.com/writing/my-ai-adoption-journey + https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
**Takeaways.**
- A markdown file at the repo root, read on every session. Build commands, conventions, architectural constraints, glossary, known traps. *Every line traceable to a past failure.*
- The corollary: *AGENTS.md is the changelog of every mistake your agents have made, written in the imperative.* Documentation **is** the harness, not overhead around it.

---

### Card 3 — *Advanced Context Engineering for Agents* (the RPI loop)

**Author / venue.** Dex Horthy (HumanLayer; author of *12-Factor Agents*) — AI Engineer Code Summit, November 2025.
**Link.** https://www.youtube.com/watch?v=IS_y40zY-hc
**Thumbnail.** [level-04/horthy-rpi.jpg](level-04/horthy-rpi.jpg) *(to be added)*
**Takeaways.**
- Three phases, three **fresh** context windows, three markdown artifacts: **Research → Plan → Implement.** The artifacts are the connective tissue, not the conversation history.
- Empirical context-fill thresholds from HumanLayer's 100k-session telemetry: **smart < 30%, warm 30–40%, dumb > 40%.** The whole RPI structure exists to keep the agent left of the cliff.
- *"You cannot outsource the thinking."* Senior engineering concentrates upstream — into research framing and plan review, not code review.

---

### Card 4 — *The ratchet method* (engineer-out-every-mistake)

**Author / venue.** Mitchell Hashimoto — *My AI Adoption Journey*, February 2026.
**Link.** https://mitchellh.com/writing/my-ai-adoption-journey
**Takeaways.**
- Every agent mistake gets engineered out **structurally** — into AGENTS.md, a linter rule, a tool wrapper, a system-prompt constraint, a new skill. **Never just re-prompted away.**
- The visceral demo: same task twice. First run, agent fails. Don't fix the output — open the harness, add the constraint that prevents the failure, re-run. The audience sees the failure *not recur*. That is the loop.

---

### Card 5 — *Guides vs sensors* (feedforward vs feedback control)

**Author / venue.** Birgitta Böckeler & Martin Fowler (Thoughtworks) — *Generating boring line-of-business software with an LLM* and the *Exploring Gen AI* memo series, martinfowler.com, 2024–2026.
**Link.** https://martinfowler.com/articles/exploring-gen-ai.html
**Takeaways.**
- Control-systems vocabulary applied to harnesses. **Guides** (feedforward) — `AGENTS.md`, conventions, typed APIs, narrowed tool definitions — *prevent* wrong behaviour. **Sensors** (feedback) — linters, tests, type checkers, code-review subagents — *detect* it.
- The diagnostic question for any harness pain: *missing guide, or missing sensor?* The budgeting rule for verification: **computational sensors first** (deterministic, milliseconds), **inferential sensors** (LLM-judges) only where they earn it.

---

### Card 6 — *Don't Build Agents, Build Skills Instead* (the architecture)

**Author / venue.** Barry Zhang & Mahesh Murag (Anthropic) — AI Engineer Code Summit, late 2025.
**Link.** https://www.youtube.com/watch?v=CEvIs9y1uog
**Takeaways.**
- The architectural backbone the harness is built around: **one universal agent + a library of skills**, not one bespoke agent per domain. The harness is what stays stable while skills come and go.
- Skills package procedural domain expertise; MCP packages connectivity. The harness is the substrate that hosts both. (Revisited from Level 02 — here it earns its place as the *architecture* the harness encloses.)

---

## Slide 5 — A tour of a real harness

The actual files of `webinar-AI/module-4.v2.01/agent-01/` — what each component is, which Level-04 idea it carries, and where to find it. Audience walks out able to clone the shape into any repo.

### `AGENTS.md` — the index, not the manual

The root file. **~50 lines**, deliberately. It states the operating contract (which input columns the agent's `predict()` will see at grading time), the V1 baseline (the floor to beat), the file layout, and **points at the per-phase READMEs for everything load-bearing.** That last move is the point: *the bytes the agent pays for every turn are an index, not the instructions themselves.* The instructions live behind one more hop — loaded fresh when the phase that needs them starts.

> *Carries:* the "AGENTS.md as artifact" idea (Card 2) **and** the per-turn token-tax discipline. The same file inverts both the *what* (a contract) and the *how* (cheap).

### `phases/{1-research, 2-plan, 3-implement}/README.md` — the RPI loop in directory form

Three sibling folders. Each ships a `README.md` (load-bearing guidance for the phase), a `PROMPT.md` (the bootstrap prompt for the fresh session), a `run.sh` (the launcher), and `artifacts/` (where the phase's output lands and gets chmod-locked).

- **Phase 1 / Research** — open context, diagnose V1's residual, list candidates. No code. Produces `RESEARCH.md`.
- **Phase 2 / Plan** — fresh context. Reads only `RESEARCH.md`. Picks 2 candidates by default (one rung-0, one structurally different). Produces `PLAN.md`.
- **Phase 3 / Implement** — fresh context. Reads only `PLAN.md` + skills + the prefilled `models/` tree. Builds, iterates via `skills/iterate`, ships `final-model/`.

The fresh-context boundary is **enforced mechanically**: `lock.sh` chmods each artifact non-writable when its phase ends, and `pre-flight-final-model` refuses the submission if a lock is missing. The agent literally cannot edit the plan during Implement. The harness encodes Horthy's *"frequent intentional compaction"* as a file-permission bit.

> *Carries:* the RPI loop (Card 3). The README.md of each phase is the load-bearing instruction; the agent only pays for it when that phase starts.

### `skills/*/SKILL.md` — the procedural recipes

The same `SKILL.md` shape introduced in Level 02, applied at harness scale. Fifteen skills cover the lifecycle: `fit-model`, `score-model`, `inspect-residuals`, `residual-structure`, `route-bias`, `critique-residuals`, `iterate`, `compare-models`, `assess-candidate-model`, `pre-flight-final-model`, `diagnose-by-physics-regime`, and supporting plumbing.

Two patterns earn the call-out:

- **`skills/iterate/` is the only skill that writes `MODELS.md` / `TREE.json`.** Every other skill is read-only on the registry. That's a *guide* in the Böckeler/Fowler sense — the harness narrows write access to a single tool, so the agent cannot accidentally corrupt the tree-search frontier.
- **`skills/critique-residuals/` is an inferential sensor.** Where `score-model` is computational (deterministic floats), `critique-residuals` is an LLM call that routes the residual to a candidate. The harness uses *both* kinds of sensor and is explicit about which is which.

> *Carries:* the architecture from Card 6 (universal agent + skills) and the verification discipline from Card 5 (sensors). The closing line in `AGENTS.md` — *"Skills and references are clay. Skill output not useful? Open the body, add what you need, save, re-run."* — is the ratchet from Card 4 turned into a working instruction.

### `references/m4-cohort-findings.md` + `references/anti-patterns.md` — the ratchet, made readable

Two files that distinguish a harness from a starter template.

**`m4-cohort-findings.md`** opens with frontmatter and a `§0 Headline` section listing four evidence-backed moves *with the agent ID that demonstrated each one*: "agent-03 shipped this for −30% yaw / −21% CTE — the m3.v3 cohort winner." Every numbered finding cites the specific REPORT.md it came from. This is the [ratchet method](#card-4--the-ratchet-method-engineer-out-every-mistake) at cohort scale — a previous cohort's failures and wins, distilled into routing advice the *next* cohort consults before it starts.

**`anti-patterns.md`** is the same loop on the negative axis. Each entry is a trap that surfaced repeatedly across the cohort, written in the imperative: *"Fit on one platform, ship for both," "Splitting train/dev at the sample level inside a segment," "Per-segment bias removal — the illegal version (don't do this)."* Each one cites why it's wrong and the structural fix.

> *Carries:* the ratchet (Card 4). Notice the artefact-level loop — the cohort produces REPORT.md files, a human (eventually, a skill — see m5) crystallises them into `references/`, the next cohort consults `references/` before starting. The harness *learns across runs* even though no individual agent has memory.

### The composite picture

The five components — `AGENTS.md`, `phases/`, `skills/`, `references/`, the registries — are not five engineering choices. They are the **six-component harness anatomy** (Card 1) instantiated in a repo:

| Anatomy component | Where it lives in Module 4 |
|---|---|
| **Tools** | `skills/*/scripts.py`, MCP-style scorers in `_shared/` |
| **Memory / state** | `MODELS.md`, `TREE.json`, `EXPERIMENTS.md` registries |
| **Context** | `phases/*/PROMPT.md` + the fresh-window boundary |
| **Planning** | `phases/2-plan/` + `skills/iterate` tree-search |
| **Verification** | `score-model`, `pre-flight-final-model`, `lock.sh` |
| **Modularity** | one skill = one folder; one phase = one folder |

This is the lesson the slide closes on. *Same model + this harness = different system.* The audience leaves with the tree and the table — they can build the next one on Monday.

*Source: internal — `webinar-AI/module-4.v2.01/agent-01/`; full thesis in that folder's `README.md` and `AGENTS.md`.*

---
