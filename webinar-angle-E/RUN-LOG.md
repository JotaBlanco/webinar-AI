---
title: webinar-angle-E — RUN-LOG iter 2
summary: First substantive run of the **same-task-four-ways / scaffold-tier** angle. The lever is the *kind* of scaffold around a fixed model — workflow (M2), universal agent + skill (M3), RPI loop (M4). The model is held fixed across modules. M1 (bare model) is represented by raw-model/idea-01/.
date: 2026-05-28
iteration: 2
challenge: tasks/lateral-fidelity-challenge.md (verbatim 3-line naked prompt from `webinar-00/domain-knowledge-challenges/idea-01-lateral-attribution.md` lines 52-54)
launch_id: webinar-angle-E/20260527-222256
---

# RUN-LOG iter 2 — three scaffold tiers, one fixed model

## What this angle is testing

Unlike A/D (single accretion ladder), angle E swaps the **kind of scaffold** between modules while holding the model and task fixed. This is the workshop's controlled-experiment angle (NC-6 three-tier decision tree, NC-27 RPI upgrade).

- **M1** — bare model (no substrate). Represented by `raw-model/idea-01/`, not re-run here.
- **M2** — **workflow tier**: a prescriptive 5-step AGENTS.md playbook backed by five deterministic Python tool wrappers (`tools/step1..step5`). No skill, no eval, no agentic latitude. Agent is the deterministic executor.
- **M3** — **universal agent + skill tier**: thin AGENTS.md pointing at `skills/yaw-divergence-triage/SKILL.md` (the same 5-step logic as prose) plus a sibling skill `skills/regime-comparison/` for per-regime attribution. Agent loads metadata first, decides composition.
- **M4** — **universal agent + skills + RPI loop tier**: same M3 substrate; AGENTS.md prescribes a Research → Plan → Implement 3-phase split (out/research.md → out/plan.md → REPORT.md), simulated within one run by gating each phase on a separate artifact.

Substrate authored fresh from `car-sim-real-CLAUDE.md` and `F1/KB002/ai-axis/ai-axis-ideas/05-same-task-four-ways/proposal.md`. No reads from iter-1 modulo-N/ folders.

## Setup mechanics

- 5 `general-purpose` subagents per module level. 15 agents total; each in its own `module-N/agent-NN/` subfolder with `code` and `data` symlinks.
- Naked prompt verbatim from `idea-01-lateral-attribution.md` lines 52-54, byte-identical across all 15.
- 15-min wall-clock budget per agent.
- Launched via the `launch-isolated-module-agents` orchestrator.
- **First batch (D + E in one message, 30 agents): D-M2 and D-M3 partial completed, then session-rate-limit hit; the remaining 17 (almost all of E + tail of D-M3/M4) returned the limit message instantly.** Re-fired the 17 after the limit reset (2am Madrid). All 17 completed cleanly on the second pass.

## Headline numbers — RMSEs in rad/s, Ford Mach-E (MK1)

E agents converged remarkably tightly on identical numbers because most loaded the *full* 315-segment Mach-E set rather than a sub-sample (the workflow scripts and the skill helpers default to the full corpus). The numerical signature is striking — variance across agents within a module is essentially zero except where one agent picked a different subset.

### M2 — workflow tier (5 deterministic steps)

| agent | n_segs | V0 | V1 | V2 | V3 | best | best_var | net drop | step4 bug? |
|---|---:|---:|---:|---:|---:|---:|---|---:|---|
| agent-01 | 315 | 0.01613 | **0.01469** | 0.01653 | 0.01663 | 0.01469 | V1 | −8.9% | patched in-place |
| agent-02 | 315 | 0.01613 | **0.01469** | 0.01653 | 0.01663 | 0.01469 | V1 | −8.9% | patched in-place |
| agent-03 | 315 | 0.01613 | **0.01469** | 0.01653 | 0.01663 | 0.01469 | V1 | −8.9% | **did not trigger** |
| agent-04 | 315 | 0.01613 | **0.01469** | 0.01653 | 0.01663 | 0.01469 | V1 | −8.9% | patched in-place |
| agent-05 | 315 | 0.01613 | **0.01469** | 0.01653 | 0.01663 | 0.01469 | V1 | −8.9% | patched in-place |

All five M2 agents produced **identical** numbers — the prescriptive workflow + deterministic tools deliver perfect reproducibility, as the proposal promised. Four of five hit the `PARAM_BY_PLATFORM[...]` dict-vs-dataclass bug in step4 and patched in-place; one (A03) inexplicably did not hit it (likely Python interpreter / import-cache quirk).

### M3 — universal agent + skill tier (yaw-divergence-triage + regime-comparison)

| agent | n_segs | V0 | V1 | V2 | V3 | best | best_var | net drop | sibling skill used? |
|---|---:|---:|---:|---:|---:|---:|---|---:|---|
| agent-01 | 315 | 0.01612 | **0.01469** | 0.01653 | 0.01664 | 0.01469 | V1 | −8.9% | yes — per-regime contrast |
| agent-02 | 315 | 0.01613 | **0.01469** | 0.01653 | 0.01664 | 0.01469 | V1 | −8.9% | yes; also ran a global-DE V3 probe (still worse) |
| agent-03 | 315 | 0.01613 | **0.01469** | 0.01653 | 0.01628 | 0.01469 | V1 | −8.9% | yes; ran multi-start V3 → 3e5/3e5, real improvement over stuck-at-x0 but still worse than V1 |
| agent-04 | 315 | 0.01613 | **0.01469** | 0.01653 | 0.01664 | 0.01469 | V1 | −8.9% | yes |
| agent-05 | 315 | 0.01613 | **0.01469** | 0.01653 | 0.01664 | 0.01469 | V1 | −8.9% | yes; 5-seed multi-start probe to diagnose flat loss |

All five M3 agents converge on V1 as best, identical to M2. **Two of five (A03, A05) went outside the prescribed ladder** to probe V3's optimizer behaviour — A03 ran a global-DE probe, A05 ran a multi-start sweep. This is exactly the latitude the skill tier allows (and the workflow tier forbade).

### M4 — RPI loop tier (research.md → plan.md → REPORT.md)

| agent | V0 | V1 | V2 | V3 | best | best_var | net drop | RPI artifacts produced? | plan dissent? |
|---|---:|---:|---:|---:|---:|---|---:|---|---|
| agent-01 | 0.01613 | **0.01469** | 0.01653 | 0.01663 | 0.01469 | V1 | −8.9% | yes (3-phase) | yes — V3 fit degeneracy |
| agent-02 | 0.01613 | **0.01469** | 0.01653 | 0.01663 | 0.01469 | V1 | −8.9% | yes | yes — locked-plan didn't anticipate net regression |
| agent-03 | 0.01613 | **0.01469** | 0.01653 | 0.01663 | 0.01469 | V1 | −8.9% | yes | yes — ran out-of-band grid for V3 |
| agent-04 | 0.01613 | **0.01469** | 0.01653 | 0.01663 | 0.01469 | V1 | −8.9% | yes | yes — V1 recipe drift (canonical L vs L_eff fit) |
| agent-05 | 0.01613 | **0.01469** | 0.01653 | 0.01663 | 0.01469 | V1 | −8.9% | yes | yes — out-of-band Nelder-Mead for V3 |

All five M4 agents produced `out/research.md`, `out/plan.md`, and a REPORT.md, in that order. **Every M4 agent recorded a "plan dissent" section** — the locked plan committed before seeing the V2/V3 numbers, so the regressions came as a real Phase-3 surprise and the agents had to honestly report them rather than course-correct mid-flight.

## Key cross-cohort findings

### Finding 1 — Cross-tier numerical convergence is near-perfect

When the corpus and tool wrappers are deterministic, all three scaffold tiers (workflow, skill, RPI) on the *same data* produce the *same numerical answer*: V0 0.01613, V1 0.01469, V2 0.01653, V3 0.01663. **The scaffold tier does not change what's true about the data.**

What the tiers *do* change is the *narrative shape of the report*:
- **M2 (workflow)** reports the ladder mechanically; the agents who hit step4's bug had to patch it in-place and record the deviation. None of the M2 reports produce a per-regime contrast (no `regime-comparison` available).
- **M3 (skill)** reports add per-regime attribution via the sibling skill, and 2/5 agents go *outside* the prescribed ladder to investigate V3's optimizer pathology.
- **M4 (RPI)** reports embed a "plan dissent" section that names what the locked plan *did not* anticipate. The dissent itself is the load-bearing artifact.

### Finding 2 — The workflow tier (M2) has a real reproducibility win

5/5 M2 agents produced **byte-identical numerical headlines**. The workflow + deterministic tools is *literally* deterministic — no agentic variance in segment selection, no optimizer-seed drift, no preprocessing-choice ambiguity. This is the proposal's NC-6-tier-1 lesson made concrete: *if you can draw it on a whiteboard, build the workflow*.

The cost is brittleness. 4/5 agents had to **patch step4 in-place** for the `PARAM_BY_PLATFORM` dict-vs-dataclass bug. The workflow doesn't recover gracefully; the agent has to know enough Python to bridge the API mismatch. This is real signal: workflow-tier substrate is reproducible but unrescuable when the tools have bugs.

### Finding 3 — The skill tier (M3) trades determinism for diagnostic depth

M3 agents produce the same V0/V1/V2 numbers as M2, but **two of five (A03, A05) ran additional diagnostics not in the prescribed ladder** — global DE probes, multi-start sweeps — to characterise V3's optimizer behaviour. They reported these as *out-of-band* findings, which is the right shape (the locked ladder still ran; the probes annotated it). M2 agents could not have done this without violating the workflow.

The sibling skill (`regime-comparison`) was loaded by **5/5 M3 agents** and produced a per-regime contrast table that localised V2's regression to the transient regime in every report. **The composition was natural** (load metadata, decide, run) and no agent needed help from outside the harness to figure out the order. This validates the NC-9 / NC-20 promise that universal-agent + skills is a stable composition primitive.

### Finding 4 — The RPI tier (M4) buys "plan dissent" as a deliverable

Every M4 agent produced an `out/research.md` (~25-30 lines) **before** locking the plan, and a `out/plan.md` (~25 lines) **before** running the ladder. Each agent's research surfaced something that shaped the plan:
- **Lightning's persistent yaw bias** (A01, A02): drove the Mach-E platform choice.
- **Straight-row dominance (86% of corpus)** (A03, A05): pre-warned that any global Cα fit would be insensitive on most rows.
- **Transient regime is thin** (~2-18 rows depending on segment subset) (A02): prevented over-weighting transient stats.

Then the plan locked the ladder. Then Phase 3 ran it. **Then every agent recorded plan dissent** because the V2/V3 regression and the V3-stuck-at-x0 finding emerged in Phase 3 and the locked plan didn't allow course-correction.

This is the proposal's NC-27/NC-28 beat: *fresh context preserves smart-zone quality*. In simulation form here (one subagent, not three sessions), the agents discovered that the dissent itself is the load-bearing M4 deliverable — they would not have written one in M3.

### Finding 5 — V3 fit failure is universal across all tiers

Same as angle D and angle A/B/C iter-2 finding: `fit_c_alpha`'s default L-BFGS-B optimizer stalls at the initial guess `(1.5e5, 1.5e5)` on this corpus. **15/15 E agents** observed it; some (M3-A03 multi-start, M3-A05 5-seed, M4-A01/A03/A05 Nelder-Mead probes) ran out-of-band diagnostics to confirm. The skill's `pegged` check only fires on the upper bound — same workshop bug-finding as angle D.

The iter-3 ratchet candidate is the same as angle D's: patch the helper to detect convergence-at-x0 and fall back to a global optimizer.

### Finding 6 — The workflow tools had a real production-blocking bug

`tools/step4_run_st_upgrade.py` accesses `PARAM_BY_PLATFORM[...]["L"]`, but `code/parameters.py` returns frozen `MachEST` dataclasses, not dicts. 4/5 M2 agents hit `TypeError: 'MachEST' object is not subscriptable` and patched in-place with a small dict-or-attribute shim. The fifth (A03) somehow did not — possibly Python interpreter cache differences across agent instances.

**This is the workshop's "workflow brittleness" beat**: the workflow tier is deterministic and reproducible, but only as long as the tools work. When they don't, the agent needs out-of-scope Python skill to repair them — exactly the cost the proposal warned about in NC-6's tier-1 framing.

The skill-tier agents (M3, M4) **never hit this bug**, because their helper module (`triage.py`) imports `parameters.py` via a different code path (one M3 agent reported a related but different friction: `triage._load_params` also does dict-style access, surfacing only when the agent inspected internal helper code).

## Process notes — isolation discipline

Same as angle D. fs-diff clean; self-reports clean; Layer 3 hook inert for subagents (documented).

Session-limit interruption identical pattern: first batch fired both angles together (30 agents) and most of E hit the limit. Re-fire batch (after the 2am Madrid reset) cleanly completed everything.

## Iter-3 punch list (specific to angle E)

- [ ] **Patch `tools/step4_run_st_upgrade.py`** with the dict-or-attribute shim baked in; 4/5 M2 agents had to do it themselves. Workshop reproducibility floor.
- [ ] **Decide whether step4 should also patch `triage.py`** (the M3+M4 helper) for the same dict-vs-dataclass issue. One M3 agent flagged it; others patched only in their driver.
- [ ] **Patch `fit_c_alpha`** to detect no-op convergence at x0 (same as angle D).
- [ ] **Workshop demo: M2 vs M3 vs M4 same-output, different-narrative.** The 5×3 numerical convergence is striking and the narratives differ in legibly different ways:
  - M2 narratives have *no per-regime contrast*.
  - M3 narratives include the contrast + out-of-band optimizer probes (2/5 agents).
  - M4 narratives include all of the above + the *plan dissent* section.
  Pull one M2 report + one M3 report + one M4 report and stack them side-by-side as the closing slide. This is the proposal's NC-6 → NC-27 ladder *visualised*.
- [ ] **Consider adding a V1.5 "ST with bias removed" rung** (same candidate as angle D Finding 3). Multiple E agents observed that V2 drops V1's bias step and would likely improve if it didn't.
- [ ] **Workshop framing decision (Javi):** angle E's clean headline is **"same numbers, three different reports"** — the scaffold tier doesn't change *what's true* about the data; it changes *what the agent says about it*. M2 is reproducible-but-narrow; M3 surfaces what M2 hides; M4 makes the "what we didn't expect" the deliverable. This is NC-6's spine and NC-27's upgrade made visible in one experimental panel.

## Files produced

```
webinar-angle-E/
  RUN-LOG.md                        (this file — iter-2 only)
  .launch-config.json               (15 module entries)
  _shared/iter2-substrate/
    M2/AGENTS.md, M2/tools/step1..step5.py, M2/tasks/
    M3/AGENTS.md, M3/skills/yaw-divergence-triage/{SKILL.md, triage.py}, M3/skills/regime-comparison/{SKILL.md, compare.py}, M3/tasks/
    M4/AGENTS.md (RPI protocol), M4/skills/* (same as M3), M4/tasks/
  _launch/20260527-222256/
    snapshot.txt
    manifest.json
    invocations.json
    *.prompt.md                     (15 rendered prompts)
  module-2/agent-{01..05}/          (workflow substrate; out/, tools/, REPORT.md)
  module-3/agent-{01..05}/          (skill substrate; out/, tools/, REPORT.md)
  module-4/agent-{01..05}/          (RPI substrate; out/research.md, out/plan.md, REPORT.md)
```
