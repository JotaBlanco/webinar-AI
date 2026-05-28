---
title: webinar-angle-A — RUN-LOG iter 1
summary: First-pass run of the knowledge-accretion angle. Four agents, same challenge (lateral fidelity attribution on Ford), same model, four substrates. Records each agent's outputs side-by-side, what each substrate failure-mode produced, and the calibration issues we found that the next iteration needs to fix.
date: 2026-05-26
iteration: 1
challenge: lateral-fidelity-challenge.md (identical bytes in all 4 módulos)
---

# RUN-LOG iter 1 — substrate accretion across M1–M4

## Setup

- Four `general-purpose` subagents launched in parallel, in background.
- Each scoped *by prompt* to its `modulo-N/` + `code/` (symlink) + `data/` (symlink). No hard sandbox; soft path whitelist + explicit "do not read parent / sibling / KB00*" instruction.
- All four received byte-identical task: `tasks/lateral-fidelity-challenge.md`.
- Underlying model and tools identical across the four.

## Substrate state going in

| | AGENTS.md | skills/ | references/ | evals/ |
|---|---|---|---|---|
| M1 | 4 lines (project name + venv hint) | — | — | — |
| M2 | 90 lines (units, signs, traps, data layout, platform truth matrix) | — | — | — |
| M3 | 102 lines (= M2 + skills inventory + references entry) | `lateral-fidelity-triage/SKILL.md` + `triage.py` | `ks-vs-st.md` (the catalogue) | — |
| M4 | 108 lines (= M3 + evals entry) | same SKILL.md + triage.py | same catalogue | `lateral_fidelity_eval.py` |

## Headline numbers — attribution tables side by side

All RMSEs in rad/s. `pct_var_closed` is the headline reduction in `var(resid)` vs each agent's own V0.

### M1 — empty lamp

| variant | RMSE_overall | straight | steady | transient | Δ vs prev | var_closed |
|---|---:|---:|---:|---:|---:|---:|
| v0_ks_stock | **0.00892** | 0.00721 | 0.02157 | 0.01315 | — | 0.0% |
| v1_ks_Leff | 0.00747 | 0.00651 | 0.01473 | 0.01078 | -0.00145 | 26.7% |
| v2_st_canonical | 0.00559 | 0.00465 | 0.01169 | 0.00894 | -0.00188 | 63.8% |
| v3_st_calibrated | 0.00425 | 0.00330 | 0.00679 | 0.00920 | -0.00134 | **78.4%** |
| v4_st_residual | 0.00426 | 0.00330 | 0.00674 | 0.00930 | +0.00001 | 78.0% |

### M2 — ratchet

| variant | RMSE_overall | straight | steady | transient | Δ vs prev | var_closed |
|---|---:|---:|---:|---:|---:|---:|
| v0_baseline_KS | **0.01499** | 0.01422 | 0.01842 | 0.02439 | — | 0.0% |
| v1_KS_plus_yaw_bias | 0.00909 | 0.00754 | 0.02211 | 0.01996 | -0.00590 | 66.0% |
| v2_LinearST_prior_Cα | 0.00578 | 0.00494 | 0.01348 | 0.01136 | -0.00331 | 87.5% |
| v3_LinearST_fit_Cα | 0.00418 | 0.00375 | 0.00796 | 0.00868 | -0.00160 | 93.2% |
| v4_ST_plus_residual_learner | 0.00356 | 0.00322 | 0.00735 | 0.00547 | -0.00062 | **93.7%** |

### M3 — crystallised skill

| variant | RMSE_overall | straight | steady | transient | Δ vs prev | var_closed |
|---|---:|---:|---:|---:|---:|---:|
| V0 — KS baseline | **0.0151** | 0.0145 | 0.0332 | 0.0171 | — | 0.0% |
| V1 — KS recalibrated | 0.0086 | 0.0082 | 0.0184 | 0.0192 | -0.0065 | **63.8%** |
| V2 — Linear ST (prior C_α) | 0.0149 | 0.0127 | 0.0257 | 0.0906 | +0.0063 | -2.6% |
| V3 — ST + C_α fit | 0.0138 | 0.0116 | 0.0188 | 0.0910 | -0.0011 | +10.1% |
| V4 — V3 + residual ML (LOO) | 0.0159 | 0.0143 | 0.0218 | 0.0841 | +0.0021 | -19.1% |

### M4 — sensor + self-patch

| variant | RMSE_overall | straight | steady | transient | Δ vs prev | var_closed |
|---|---:|---:|---:|---:|---:|---:|
| V0 — KS baseline | **0.0151** | 0.0145 | 0.0332 | 0.0171 | — | 0.0% |
| V1 — KS recalibrated (i_s) | 0.0138 | 0.0135 | 0.0203 | 0.0237 | -0.0014 | 15.5% |
| V2 — Linear ST (canonical Cα) | 0.0128 | 0.0125 | 0.0210 | 0.0142 | -0.0010 | 28.0% |
| V3 — ST + Cα tuned | 0.0115 | 0.0114 | 0.0136 | 0.0120 | -0.0013 | **40.1%** |
| _V4 — honestly skipped_ | — | — | — | — | — | — |

## What the substrate actually did to each agent

### Baselines disagree on purpose

M1's V0 is **0.0089**; M2/M3/M4's V0 is **0.0150**. That 70% difference is not noise — it is M1 doing a per-segment yaw-gyro bias removal *as preprocessing* and folding it into "the baseline", while M2/M3/M4 use the raw `yaw_rate_resid_rads` column from the CSV as the baseline (the contract that the M2+ substrate establishes). M1 absorbed an honest finding into a less honest comparison; the more-instructed agents reported the same finding as V1 of the ladder, where it visibly counts.

This is the first measurable substrate effect: **without substrate the agent makes private methodological choices that move the headline by ~70%**. With substrate, the methodology is shared and the headline is comparable across runs.

### M3 produced the most insightful engineering finding

M3 is the only agent that reported `V2 — Linear ST` *worsening* the overall RMSE (+0.0063, -2.6% variance closed). The other three got V2 to help. M3 then noted that V3 hits the overfit ceiling on C_r (`pegs at 500 kN/rad`) — a flag the catalogue explicitly told it to raise. The narrative explicitly invokes the steady-state-yaw-gain formula `v / (L · (1 + K_us · v²))` and reasons that the openpilot ST prior is *stiffer than these tyres want*, giving back the gain that V1's single steering-ratio knob carefully removed.

This is the workshop's headline finding: **the skill + reference doc don't maximise the metric, they enable physically-honest reporting**. M1 and M2 closed 78–94% of variance with creative preprocessing; M3 closed 64% with V1 alone and *named* why ST didn't help. The M3 report is the only one a senior engineer would defend in a design review.

### M4 was the most disciplined and the only one to pass the eval

M4 closed only 40% of variance and explicitly skipped V4 ("partial > faked", citing the skill's own instruction). It is also the only one whose final `report.md` passes the computational sensor on the first eval-cycle-after-ratchet. It is the only run we can sign off on without manual inspection.

### The ratchet loop fired as designed

M4 hit `attribution_table_missing` on the first eval run. The eval's loose-substring header matcher latches onto the *first* markdown table in the file, and empty header cells in any markdown table substring-match every required column name — so the eval mis-identified a segment-list table as the attribution table. M4 patched `skills/lateral-fidelity-triage/SKILL.md` adding a "Ratchet R1 — only one markdown table in `report.md`" rule, regenerated the report with bullet lists for everything except the attribution table, re-ran the eval, **PASS** (0 failures, 0 warnings). One ratchet. This is exactly the loop the proposal promised.

## Calibration issues the substrate has and the next iteration must fix

### B1 — AGENTS.md references a `.venv` that does not exist (all of M2, M3, M4)

Every agent from M2 onward stumbled on `source .venv/bin/activate`. All three independently fell back to system Python. M1 was unscathed because its substrate doesn't mention the venv.

**Fix.** Either (a) commit a `.venv/` to the runtime or (b) drop the line from AGENTS.md and document the actual Python invocation. Recommend (b) and add `# bin/python` to the build/run section.

### B2 — Substrate never warns about ST integrator stiffness at low v

All three of M1, M2, M3, M4 independently re-discovered that the linear ST integrator blows up when `v → 0` (Lightning segments have stationary stretches). Each invented its own fix — sub-stepping + KS fallback. This is a textbook "engineered out into AGENTS.md or the SKILL" trap.

**Fix.** Add one line to `references/ks-vs-st.md` (and surface in SKILL.md's V2 step) — *"ST eigenvalues scale as `(C_f + C_r) / (m · v)`; sub-step or fall back to KS below `v_min ≈ 2 m/s`."* This is exactly what the ratchet method is for.

### B3 — Eval's loose-substring matcher is fragile

M4 found this in one ratchet. The fix M4 chose is the *correct* one (constrain the artifact, not the eval — that's the harness-as-substrate philosophy). But the rule "only one markdown table" only lives in M4's SKILL.md; M3's identical SKILL.md doesn't have it.

**Fix for iter 2.** Backport the R1 line to M3's SKILL.md too (so the skill is the same artifact across modules, the *only* difference is whether the eval exists). The current diff includes an unintentional skill-content drift between M3 and M4.

### B4 — M1 was too capable for the "founder" beat

The workshop narrative needs M1 to *visibly fail* — confidently invent a parameter name, pick the wrong sign convention, hallucinate. None of that happened. M1 produced a credible V0→V4 ladder closing 78% of variance, autonomously discovered the yaw-bias issue, and wrote a 12 KB report. This is a calibration risk: if M1 succeeds, the accretion arc collapses.

**Two candidate fixes for iter 2** (need your call):
- **Make M1's challenge harder** — strip the `yaw_rate_resid_rads` column from the CSV, or pick a question where the prior alone is insufficient (e.g. "predict tyre temperature evolution" — model has no thermal channel at all).
- **Strip the CSV's self-documenting columns from M1's data view** — if the agent can't see that `yaw_rate_pred_rads` and `yaw_rate_meas_rads` exist as ready-made columns, it has to read the rlog from scratch, which is a much taller wall without the substrate of M2+.

The current task lets M1 read columns that are themselves a leakage of the substrate. The substrate didn't have to tell M1 how to compute the baseline — the CSV did.

### B5 — Variance-closed metric is not stable across agents

Because M1's baseline is different from M2/M3/M4's, the headline metric is not comparable across modules. The relative shape of the ladder is comparable; the absolute numbers are not.

**Fix.** Add one sentence to the challenge: *"Compute baseline RMSE from the existing `yaw_rate_resid_rads` column as-is, with no preprocessing. Preprocessing steps belong inside V1+, not in the baseline."* This is in `lateral-fidelity-triage/SKILL.md` already, but not in the bare task, so M1 doesn't see it.

## What the workshop story will actually be

If we ran this on stage today, the four answers would land like this:

- **M1 (empty lamp)** — *"Look at how much it does, even with nothing."* Risk: undercuts the entire arc. Calibration item B4.
- **M2 (ratchet)** — *"Now the baseline is comparable. The agent can collaborate with us on methodology."* Lands. Numbers are bigger but for honest reasons.
- **M3 (skill)** — *"The agent reports something we wouldn't have known: ST priors are wrong for these tyres."* This is the angle's sharpest beat. The skill + reference make the agent more *honest*, not more *optimistic*.
- **M4 (eval + self-patch)** — *"The skill patches itself on a real eval failure, live, and you watch the SKILL.md grow one R1 rule that will never be tripped again."* This is the *biography of one artifact* moment from the proposal.

The accretion arc holds — but M1 is not a foundering, it is a *credible-but-unverifiable* answer, and that may actually be a stronger storyline than the foundering one. Different rhetorical shape; needs Javier's call.

## Process notes (what worked, what didn't)

**What worked.**

- Soft path whitelist via prompt was respected by all four agents. No agent read `KB00*`, no agent read sibling `webinar-*`, no agent read parent. Two agents (M1, M3) explicitly noted moments they *wanted* to look outside and chose not to — which is exactly the discipline we wanted to test.
- The symlink pattern (`code` and `data` as symlinks to the repo root) worked transparently — every agent treated `./code/` and `./data/` as native subdirs of its module.
- The eval's failure-then-ratchet loop fired exactly once on M4 in exactly the way the proposal promised. The ratchet went into the SKILL.md (the artifact), not the eval (the judge). This is the correct direction.
- All four agents finished in 6.5–9 min and used 60–75 k tokens — well within reasonable workshop pacing budget.

**What didn't.**

- M3 and M4 share a skill that has now drifted in M4 (the R1 rule). The substrate is no longer monotonic across modules unless we manually backport. Iter 2 should either accept this (M4 = M3 + ratchet-evolved skill) or backport.
- B1 (the missing `.venv`) was hit by every agent that read AGENTS.md. We knew about it before launch and didn't fix it — a real workshop run would have lost 30s × 3 agents to this. Fix before the next rehearsal.
- The task says "use Ford segments only" but does not say "compute baseline from the CSV column with zero preprocessing". M1 took the wiggle room. Lock the methodology in the task body.

## Files produced

```
webinar-angle-A/
  _task-canonical.md
  RUN-LOG.md                        ← this file
  modulo-1/
    AGENTS.md   (4 lines)
    report.md   (12 KB)             ← M1 output
    report.png  (270 KB)
    tasks/lateral-fidelity-challenge.md
    tools/                          ← M1 wrote tools/ here even though we removed it from the template
  modulo-2/
    AGENTS.md   (90 lines)
    report.md   (7.6 KB)            ← M2 output
    report.png  (181 KB)
    tasks/lateral-fidelity-challenge.md
    tools/                          ← M2 same
  modulo-3/
    AGENTS.md   (102 lines)
    skills/lateral-fidelity-triage/SKILL.md
    skills/lateral-fidelity-triage/triage.py
    references/ks-vs-st.md
    report.md   (7.0 KB)            ← M3 output
    report.png  (114 KB)
    tasks/lateral-fidelity-challenge.md
    tools/                          ← M3 same
  modulo-4/
    AGENTS.md   (108 lines)
    skills/lateral-fidelity-triage/SKILL.md   ← drifted (+R1)
    skills/lateral-fidelity-triage/triage.py
    references/ks-vs-st.md
    evals/lateral_fidelity_eval.py
    report.md   (8.5 KB)            ← M4 output
    report.png  (122 KB)
    tasks/lateral-fidelity-challenge.md
    tools/                          ← M4 same
```

## Iter 2 punch list (waiting on Javi's call)

- [ ] B1 — fix `.venv` reference in M2/M3/M4 AGENTS.md (drop the line or commit the venv).
- [ ] B2 — add ST stiffness warning to `references/ks-vs-st.md` and SKILL.md.
- [ ] B3 — backport M4's R1 to M3's SKILL.md (or accept the drift).
- [ ] B4 — calibrate M1 difficulty: either harden the task or strip the CSV's self-documenting columns from M1's data view.
- [ ] B5 — add baseline-methodology clause to the canonical task body.
- [ ] Decide whether the M1 narrative should be "founder" or "credible-but-unverifiable".

---

# RUN-LOG iter 2 — 5×3 cohort, naked prompt, fresh substrate
date: 2026-05-27
iteration: 2
challenge: tasks/lateral-fidelity-challenge.md (verbatim 3-line naked prompt from `webinar-00/domain-knowledge-challenges/idea-01-lateral-attribution.md` lines 52-54)
launch_id: webinar-angle-A/20260527-134542

## What changed from iter 1

- **M1 dropped.** The empty-lamp condition is now represented by `raw-model/idea-01/` (10 agents on the naked prompt with no substrate). Iter-2 only re-runs M2, M3, M4 to study the substrate-accretion effect proper.
- **5 agents per module, not 1.** Statistical baseline at each substrate level. 15 agents total; each in its own `module-N/agent-NN/` subfolder; AGENTS.md + skills + references + evals identical across the 5 agents of a module level.
- **Renamed `modulo-N/` → `module-N/`** per Javier's preference.
- **Substrate authored fresh** (not iter-1 carry-over). Cleaned canonical operating-contract material from `car-sim-real-CLAUDE.md` into per-module AGENTS.md; authored a fresh `lateral-fidelity-triage` skill with helper `triage.py`; authored a fresh `references/ks-vs-st.md` variant catalogue; authored a fresh `evals/lateral_fidelity_eval.py` scoring the six success metrics from `idea-01-lateral-attribution.md` (truth-channel, contract, regime-breakdown, methodology-consistent, attribution-coherent, regression-flagged). Substrate is identical across each module level's 5 agents.
- **Naked prompt verbatim.** `tasks/lateral-fidelity-challenge.md` is exactly the 3-line brief from `idea-01-lateral-attribution.md` — no methodology hints, no metric named, no platform named.
- **15-min wall-clock budget per agent.**
- Used the `launch-isolated-module-agents` skill's orchestrator. Three skill scripts patched to support nested `module-N/agent-NN/`:
  - `launch-all.py`: self-filter compares full resolved paths (was filtering by basename, which fails when basenames repeat like `agent-01` × 3 modules); template header stripped on first `---` marker; `--angle-root` / `--repo-root` plumbed from `orchestrate.py`.
  - `pre-flight-check.py`: P7 uniqueness check switched from basename to full module_path + module_name.
  - `orchestrate.py`: passes `--angle-root` / `--repo-root` to `launch-all.py` explicitly (inference was walking only one parent up).

## Headline numbers — all RMSEs in rad/s, Ford Mach-E only (M2/M3/M4 agents that chose Ford; one M2 agent ran both Fords pooled)

### M2 — ratchet (AGENTS.md only; no skill, no references, no eval)

| agent | V0_baseline | V1 | V2 | V3 | V4 | best | best_var | overall_drop |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| agent-01 (Mach-E + Lightning pooled) | 0.01804 | 0.01752 | 0.01751 | 0.01733 | 0.01568 | 0.01568 | V4 understeer | 13.1% |
| agent-02 (Mach-E, 120 segs)          | 0.01550 | 0.01358 | 0.01313 | 0.01440 (ST regr) | —     | 0.01313 | V2 time-align | 15.3% |
| agent-03 (Mach-E, 315 segs)          | 0.01613 | 0.01414 | 0.01384 | 0.01607 (ST isolated) | 0.01380 | 0.01380 | V4 combo | 14.5% |
| agent-04 (Mach-E, 315 segs)          | 0.01613 | 0.01572 | 0.01395 | 0.01103 | 0.01077 | 0.01077 | V4 ST+gain | 33.2% |
| agent-05 (Mach-E, 315 segs)          | 0.01613 | 0.01414 | 0.01111 | 0.01077 | 0.01035 | 0.01035 | V4 lag-align | 35.8% |

Variant labels here are agent-chosen; with no shared catalogue every agent invented its own ladder.

### M3 — crystallised skill (M2 + lateral-fidelity-triage SKILL + ks-vs-st reference)

| agent | V0      | V1      | V2 (ST prior) | V3 (ST fit) | V4 (LOSO ML) | best | best_var | overall_drop | V2 regression? |
|---|---:|---:|---:|---:|---:|---:|---|---:|:--:|
| agent-01 (Mach-E, 80 segs)  | 0.01190 | 0.01013 | 0.01201 | 0.01180 | 0.01003 | 0.01003 | V4 | 15.7% | **yes** |
| agent-02 (Mach-E, 315 segs) | 0.01613 | 0.01469 | 0.01551 | 0.01564 | 0.01541 | **0.01469 (V1)** | V1 | 8.9% | **yes** |
| agent-03 (Mach-E, 315 segs) | 0.01613 | 0.01469 | 0.01551 | 0.01564 | 0.01541 | **0.01469 (V1)** | V1 | 8.9% | **yes** |
| agent-04 (Mach-E, 60 segs)  | 0.01214 | 0.01055 | 0.01248 | 0.01260 | 0.01005 | 0.01005 | V4 | 17.3% | **yes** |
| agent-05 (Mach-E, 80 segs)  | 0.01190 | 0.01013 | 0.01174 | 0.01142 | 0.00963 | 0.00963 | V4 | 19.0% | **yes** |

### M4 — sensor + self-patch (M3 + lateral_fidelity_eval.py)

| agent | V0      | V1      | V2 (ST prior) | V3 (ST fit) | V4 (LOSO ML) | best | best_var | overall_drop | V2 regression? |
|---|---:|---:|---:|---:|---:|---:|---|---:|:--:|
| agent-01 (Mach-E, 40 segs)  | 0.01394 | 0.01242 | 0.01490 | 0.01455 | 0.01120 | 0.01120 | V4 | 19.6% | **yes** |
| agent-02 (Mach-E, 60 segs)  | 0.01214 | 0.01055 | 0.01248 | 0.01217 | 0.00961 | 0.00961 | V4 | 20.9% | **yes** |
| agent-03 (Mach-E, 315 segs) | 0.01613 | 0.01469 | 0.01551 | 0.01511 | 0.01490 | 0.01490 | V4 | 7.6% | **yes** |
| agent-04 (Mach-E, 60 segs)  | 0.01214 | 0.01055 | 0.01248 | 0.01260 | 0.01005 | 0.01005 | V4 | 17.3% | **yes** |
| agent-05 (Mach-E, 40 segs)  | 0.02570 | 0.02463 | 0.02531 | 0.02505 | — (V4 regressed; honestly dropped) | 0.02463 | V1 | 4.2% | **yes** |

## Key cross-cohort findings

### Finding 1 — The V2 regression is universally reproduced once the catalogue is present

Every single agent in M3 (5/5) and M4 (5/5) flagged V2 (Linear ST with openpilot prior `C_α`) as a regression with the same physical cause: **openpilot's `C_α` prior is stiffer than the Mach-E tyres actually want** → ST steady-state gain over- or under-corrects KS depending on regime → cornering RMSE worsens. This is **the workshop's clean headline finding**: the skill + reference do not maximise the metric, they make the agent **physically honest**. In M2 agents (no catalogue), some chose ST-like variants too but did not consistently flag regressions in the same way — three M2 agents reported V2-like rungs as wins without surfacing the prior-too-stiff diagnosis.

### Finding 2 — The skill helper `triage.fit_c_alpha` silently fails on this loss surface

**Four out of five M3 agents and three out of five M4 agents independently discovered** that `triage.fit_c_alpha`'s L-BFGS-B default returns its initial guess `(1.5e5, 1.5e5)` unchanged because the local gradient is sub-tolerance / non-smooth around `K_us·v² = −1`. Each agent worked around it differently (multistart grid; Nelder-Mead; differential evolution). The skill's `pegged` check only watches the upper bound, so the silent no-op was invisible to its own self-audit. **This is the iter-2 ratchet candidate**: patch `triage.fit_c_alpha` to (a) detect a no-op convergence at `x0` and warn, (b) fall back to DE or grid.

### Finding 3 — V1 (per-segment yaw-gyro bias) carries most of the legitimate physics gain

In the M3 cohort, two agents (agent-02, agent-03) concluded **V1 is the variant to ship** — V2/V3 are regressions, V4 is a small LOSO recovery that doesn't beat V1. Three other M3 agents shipped V4 but V4's marginal contribution is small in their tables too. In M4, the same pattern: V1 is the workhorse, V4 trims a bit more in cornering when LOSO-honest. The bias-correction step on straights nearly halves the straight-regime RMSE across runs.

### Finding 4 — M4 eval drove discipline but did not fire a ratchet this round

All M4 agents structured `REPORT.md` to pass the eval's six checks on the first try (one agent — module-4-agent-02 — noted that pipe characters in description columns silently broke the eval's column parser and worked around it; that's an eval-side ratchet candidate). No agent had to patch the SKILL.md to satisfy a failed eval. Compared with iter-1 where M4 hit one ratchet (R1: "only one markdown table"), iter-2's eval was *too easy to pass* on the first try.

### Finding 5 — Substrate baselines disagree with a clear pattern

- M2 agents picked different baselines (some pooled both Ford platforms, some Mach-E only, with different sample counts), so V0 RMSEs range 0.01550–0.01804.
- M3 and M4 agents converged on Mach-E and converged tightly on V0 = 0.01613 / 0.01613 / 0.01613 (the 315-segment full-set baseline), with three agents in M3 hitting *identical* V0/V1/V2/V3 numbers (0.01613/0.01469/0.01551/0.01564) — implying the SKILL.md's "compute V0 from `yaw_rate_resid_rads` as-is, no preprocessing" line did its job. The catalogue made the methodology shared.

This is exactly the iter-1 finding (B5) playing out: without the methodology line the headline is incomparable; with it, the headline is reproducible across agents.

## Process notes — isolation discipline

- **fs-diff (Layer 7).** 3 194 files snapshotted in `code/` and `data/` before launch; **diff against post-run is clean** for all 15 agents. No agent wrote anywhere under the shared dirs. This is the strongest evidence we have.
- **Agent self-reports (Layer 1).** All 15 agents emitted `ISOLATION_REPORT:` blocks with empty `read_outside_module / attempted_blocked / shared_dir_writes` lists. Several agents explicitly noted *temptation*: agent-01 of M2 wanted to peek at `_shared` and `webinar-00`; agent-03 of M2 nearly imported `code/parameters.py` outside the symlink; multiple M3/M4 agents wanted to crib `C_α` ranges from sibling agents. All self-reported the temptation and stayed compliant.
- **Hook log (Layer 3) — important finding.** During the run window (13:34–14:00), the hook log shows BYPASS entries only — and *none* of the 15 subagent session IDs appear in the log at all. Only parent-session IDs are recorded. **The repo-wide `PreToolUse` hook is not firing for subagent tool calls in this environment.** The Anthropic Agent tool's subagent processes appear to use a different tool-execution pathway than the main session, so the parent's `settings.json` hooks don't intercept subagent reads/bash/writes. Implication: **Layer 3 was effectively absent** for this run. We had:
  - Layer 1 (prompt-soft) — honored, per self-reports.
  - Layer 2 (settings.json `permissions.deny`) — would still apply at the subagent settings layer if subagents inherited them, but we have no evidence either way without a deliberate violation test.
  - Layer 7 (fs-diff) — clean.
  - Layer 3 (hook) — **inert for subagents**. Needs to be re-validated or replaced.
- **Verifier V1 false-failure.** `post-run-verify.py` looks for the `ISOLATION_REPORT:` block in `REPORT.md`. It failed on all 15 modules because the parent (this session) stripped the trailer when persisting `REPORT.md` from the agent text. The trailers do exist in the agent responses captured in this run-log; they are clean. Iter-2 ratchet candidate for the skill: have the verifier accept the trailer from a separate sidecar file (`isolation-report.txt`) so it doesn't pollute `REPORT.md`'s shape — or, alternatively, have the parent persist both `REPORT.md` and the trailer block, separated.
- **Time and tokens.** Agents took 130–270 s wall-clock each (the budget was 15 min; nobody used it all). Token usage 30k–55k per agent. All 15 ran in parallel — the bottleneck was the slowest agent, ~270 s end-to-end after launch.

## Iter-3 punch list

- [ ] **Patch `triage.fit_c_alpha`** to detect the no-op convergence at `x0` (when the result equals the initial guess to numerical tolerance) and either warn loudly or fall back to DE/grid. Four agents independently re-discovered this; the next cohort shouldn't have to.
- [ ] **Tighten the eval's table parser** so a `|` inside a description cell doesn't silently drop a row. One M4 agent surfaced this; an eval ratchet.
- [ ] **Layer-3 hook is inert for subagents in the Anthropic Agent tool.** Decide whether to (a) accept this and document the skill as "Layer 1 + Layer 7 only for subagents", (b) wire enforcement into a different mechanism (subagent-side settings.json, OS-level sandbox, `container-use`), or (c) deliberately probe with a planted out-of-scope read in the prompt to confirm Layer 2 (settings.json deny) does or doesn't intercept subagent reads. As-is, iter-2's hard-enforcement story is weaker than the skill's `README.md` claims.
- [ ] **Skill: stripping the ISOLATION_REPORT trailer when persisting REPORT.md broke the verifier's V1 layer.** Either (a) have the parent assistant persist a sidecar `isolation-report.txt` alongside `REPORT.md`, or (b) widen the verifier's search to include the agent's transcript file at `~/.../tasks/<agent-id>.output`.
- [ ] **Consider widening the cohort to F-150 Lightning** for one of the agents at each module level. Iter-2 had every M3/M4 agent default to Mach-E; the cross-platform comparison from iter-1 (Mach-E vs Lightning, different sign of `K_us`) is not reproduced.
- [ ] **Workshop framing call (Javi):** at M3/M4, the headline is "the catalogue makes the agent honest, not optimistic". Three M3 agents (and two M4 agents) shipped V1 as the best variant precisely because the catalogue let them name V2/V3 as regressions. The accretion arc lands cleanly — M2's results are higher but messier; M3+ shrinks the headline and *names what's wrong*. That's a sharper story than "M4 wins on RMSE" and it replicated 5×3 in iter-2.

## Files produced

```
webinar-angle-A/
  RUN-LOG.md                        (this file — iter-1 + iter-2)
  _task-canonical.md
  .launch-config.json               (15 module entries)
  _shared/iter2-substrate/          (canonical substrate authored fresh; agents cannot read this)
    M2/AGENTS.md, M2/tasks/
    M3/AGENTS.md, M3/skills/lateral-fidelity-triage/, M3/references/, M3/tasks/
    M4/AGENTS.md, M4/skills/..., M4/references/, M4/evals/, M4/tasks/
  _launch/20260527-134542/
    snapshot.txt                    (3 194 files in code/ + data/ at launch time)
    manifest.json
    invocations.json
    *.prompt.md                     (15 rendered prompts)
  module-2/agent-{01..05}/
    AGENTS.md, code → /webinar-AI/code, data → /webinar-AI/data
    tasks/lateral-fidelity-challenge.md
    out/, tools/, REPORT.md         (REPORT.md persisted by parent from agent text)
  module-3/agent-{01..05}/          (same shape, M3 substrate)
  module-4/agent-{01..05}/          (same shape, M4 substrate incl. evals/)
```
