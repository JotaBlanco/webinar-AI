# Angle-C — process log

> Outside the modules. Captures what worked, what didn't, observations on each agent's behaviour. The four modules are isolation-enforced by written rule + agent cwd. This file is the workshop driver's notebook.

## Run #1 — initial parallel launch

**Date:** 2026-05-26
**Challenge:** lateral fidelity of the KS model with quantified ablation (see `_shared/CHALLENGE.md`).
**Baseline (computed before launch, with `evals/baseline_rmse.py`):**
- Mach-E: RMSE ψ̇ = 0.42 °/s (corr 0.88)
- F-150: RMSE ψ̇ = 1.06 °/s (corr 0.96)
- 2 segments per platform — small N. Mind variance in agent reports.

**Agents launched:** 4 in parallel (general-purpose), one per module.

**Isolation enforcement:** rule-based. Each agent's launch prompt repeats:
- cwd = `webinar-angle-C/modulo-N/`
- allowed read: cwd subtree + `code/` (symlink) + `data/` (symlink)
- forbidden: any other modulo-*, KB001/KB002/KB003, webinar-angle-A/B, _shared/
- writes: `modulo-N/out/` and `modulo-N/REPORT.md` only

### Observations (to fill once agents return)

**M1 (bare harness):** _(returned 4m53s)_
- What it did: measured baseline (Mach-E 0.51 / F-150 1.10 °/s), proposed 3 fixes (yaw-bias, steering-scale, lag), ran ablation with **interleaved** train/test split, ranked impact, shipped numbers + caveats.
- Where it stumbled:
  - **First ablation used a contiguous 70/30 split → over-fit catastrophically** (B2 = 0.73 °/s held-out). Caught it itself and fixed. Exactly the kind of failure that an `evals/` (verification) component would catch *before* over-fitting; the agent had to re-do work because nothing flagged it.
  - **Mach-E `a_y` RMSE degraded** under the corrections — agent reported this honestly, so this is signal, not failure.
- Harness friction observed: **the sub-agent's own system prompt blocked writing REPORT.md** ("Do NOT Write report/summary/findings/analysis .md files"). Agent returned the report content in text; facilitator persisted it manually. This is a real-world demo of why M2's AGENTS.md matters: even the agent's own internal "memory" had a rule about not writing reports.
- Path-isolation near-miss: nearly ran `find` from `webinar-AI/` root which would have walked into other modules; self-caught.
- Most painful absence (per the agent): **structured memory / AGENTS.md**. Quote: "A 30-line AGENTS.md would have saved ~30% of the wall-clock." Second: a pre-authored ablation skill (would have prevented the contiguous-split mistake). Third: evals. RPI loop ranked least missed.
- Quality of REPORT.md: high. Tables, ranking, limitations section all present. Numbers internally consistent and reproducible.

**M2 (+ memory/state):** _(returned 5m13s)_
- Compared to M1: implemented MORE variants (bias + lag + wheelbase, not just bias) in the same wall-clock, and reached numerically better numbers (Mach-E 0.08 vs M1's 0.39, F-150 0.53 vs M1's 0.62 with stacked). The agent attributes the speed-up to the AGENTS.md eliminating re-derivation work.
- Did AGENTS.md prevent a predicted M1 failure? **Yes, concretely:** the agent reports it was about to write `bias = median(pred − meas)` and the sign-convention line ("resid = meas − pred. Always.") caught it. Without that, M2 would have inverted the ranking and shipped A1 as "harmful". Direct demo of the ratchet method working.
- New failures observed: the M2 agent's A1 numbers are per-segment bias — that overfits to the segment's gyro zero, not a generalisable improvement. A skill like `ablation-study` (M4's) explicitly disciplines "additive monotone variants" and would have flagged it. The agent itself notes this in its honesty section ("honestly a sensor-zero calibration, not a model improvement").
- Most painful absence (per the agent): **skills library**. Different gap than M1 named. "I spent ~40% of budget hand-rolling load CSV/RMSE/group-by-regime/ablation-table workflow."
- Same harness friction as M1: sub-agent system prompt blocked writing REPORT.md. Persisted manually.
- Quality of REPORT.md: high. Better failure-honesty section than M1; explicitly calls out that bias correction is calibration not physics.

**M3 (+ planning + verification):** _(returned 6m36s)_
- Did it follow the RPI loop? **Yes, end-to-end.** Wrote `rpi/runs/20260526-010104/{research,plan,implement-notes}.md` in sequence with locked-plan discipline.
- **RPI demonstrably changed the outcome.** Agent reports: the locked plan made it ship a "principled-but-weak" result honestly instead of silently pivoting to *fit* `K_us` when canonical physics didn't explain the F-150 highway slope of 0.45. Quote: "The plan made me ship the principled-but-weak result honestly and report 'A is not worth it, the slope=0.45 is unexplained' rather than retrofit a fitted K_us and pretend physics did the work." This is the single most workshop-load-bearing moment across all 4 agents.
- Did `evals/schema_check.py` catch anything? **Yes, concretely.** Agent says it would have rejected the first draft of variant B because the agent updated `yaw_rate_pred_rads` but forgot to update the coupled `a_y_pred = v·ψ̇`. Schema check's 1e-6 sign-convention assertion on `a_y_resid` would have flagged it. Caught at code-review before run, but only because the agent ran the check.
- Did baseline match `evals/baseline_rmse.py`? **Yes, to 4 decimals.** 0.4155 / 1.0607 °/s. (Matches the pre-launch baseline I measured.)
- Numbers comparison: M3's headline is the same "+A+B" structure as M2's. The "−79%" Mach-E result is the same per-segment-bias overfit. M3 is *honest about this* in writing where M2 was honest in the failure-honesty section only. M3 also surfaced the F-150 slope=0.45 mystery that neither M1 nor M2 named.
- Most painful remaining absence (per the agent): **skills library**. Same diagnosis as M2 ("40% time on plumbing"). Both M2 and M3 converged on this.
- Same harness friction: REPORT.md write blocked. Content persisted manually + also captured by the agent in `implement-notes.md`.
- Quality of REPORT.md: highest of the three so far. Has falsifiable success criterion, explicit deferred-for-honesty section, surfaces a real open scientific question.

**M4 (+ modularity / full harness):** _(returned 8m23s)_
- Did it load skills metadata-first? Effectively yes — read frontmatters first, deferred bodies until phase 3 where each was needed.
- Did it use yaw-bias-correction as variant A? **Yes**, exactly as the harness suggested (k value F-150 = −0.01524 rad/s, Mach-E = +0.00551 rad/s).
- **Did it author any new skill?** **Yes — `skills/sim-csv-hygiene/`** (SKILL.md + normalise.py on disk, confirmed). Created in response to a real, recurring failure: `evals/schema_check.py` rejected 3/4 baseline CSVs with `a_y_resid sign wrong (max diff 1.0e-06)` — a pandas float round-trip at the exact tolerance. The agent walked the workaround once, crystallised into a skill, reused 3× across variants. **This is the NC-18 walk → crystallise → patch loop landing live in the workshop, on a real failure, not staged.**
- Component ranking from the only agent that had all six: **verification > planning > modularity**. Quote: "Without [schema_check] the FP round-trip would have silently propagated across all three variants. RPI was a close second... Skills/modularity earned the *least* of its keep on this specific challenge size... the value showed up only when the new sim-csv-hygiene skill got reused 3×."
- Caught a real overfit: the Mach-E `k=1.0` boundary in variant B looks like a "−9.3% win" in a bare table. The pre-committed physical criterion in `plan.md` outed it.
- Same harness friction: REPORT.md write blocked. Persisted manually.
- Quality of REPORT.md: highest of the four. Explicit "honest read" sections, falsifiable physical criterion, fitted-vs-canonical comparison, on-the-fly skill authoring documented.

### Cross-module narrative — the workshop's load-bearing comparison

- **Failures that M1 hit and M2 didn't:**
  - M1 nearly inverted sign convention (`bias = median(pred − meas)` instead of `meas − pred`). M2 caught it via AGENTS.md line 21. **Memory worked.**
  - M1 used a contiguous train/test split → catastrophic overfit on B2 → had to re-do. M2 had no such ratchet entry (M1's failure wasn't yet a known trap), but M2's wheelbase fit happened to use per-segment which has the same shape of issue.
- **Failures that M2 hit and M3 didn't:**
  - M2 reported A1 (per-segment bias) as a "−79% win" without flagging that per-segment fitting is essentially memorising the segment. M3, with the RPI loop, *locked* a physical falsification criterion before implementing, and consequently called out variant B (per-seg bias) as cosmetic rather than load-bearing. **Planning worked.**
  - M3's schema_check would have caught M2's coupled-pred bug (M2 updated `yaw_rate_pred_rads` without re-thinking `a_y_pred`; M3's check caught the analogue at coding time).
- **Failures that M3 hit and M4 didn't:**
  - M3 paid 40% of its time on CSV-plumbing (load → recompute → re-emit). M4 had `skills/baseline-residual/` + `skills/ablation-study/` ready and skipped that plumbing. **Modularity worked.**
  - M3 detected but couldn't *fix* the float round-trip issue cleanly — its `schema_check.py` would have flagged it but the agent didn't surface the fix as a reusable artifact. M4 not only fixed it but crystallised it into a new skill. **This is the difference between "I have evals" and "I have evals + the modularity to ratchet what evals find into reusable skills."**
- **Things M4 did that none of the earlier modules attempted:**
  - Authored a new skill mid-task in response to a sensor failure.
  - Pre-committed a *physical* (not numerical) success criterion (`corr(resid, |a_y|)` must drop on F-150). This is the kind of criterion the RPI templates suggest but only M4 actually used.
  - Honest "−9.3% Mach-E delta but k=1.0 means unidentifiable" call-out, attributable to the locked plan.

### Component-keep ranking convergence

Each agent named what it most missed:
- M1 (had only tools + braindump): **memory**.
- M2 (had memory): **skills**, with evals second.
- M3 (had memory + planning + evals): **skills**.
- M4 (had everything): in retrospect ranked what *earned its keep*: **verification > planning > modularity**.

The convergence is meaningful for the workshop:
- Agents missing component X consistently *name* X as the gap. (Direct demand signal.)
- The agent that had everything ranked verification highest. (Direct evidence that the verification component is load-bearing even when other components are present.)
- Modularity ranked lowest *until* it got used to ratchet a real failure, at which point it was indispensable. This is the BettaTech sequence: skills earn their keep only after evals reveal what to crystallise.

### Iteration notes

**What I'd change about each module's substrate before the next run:**
- Universal across all 4: **find a way around the sub-agent-system block on writing `.md` reports.** All 4 agents hit this. The challenge demands REPORT.md as a deliverable; the sub-agent harness blocks it. For the live workshop this would be confusing. Options: (a) rename deliverable to REPORT.txt or REPORT.json; (b) launch agents with a custom system prompt that strips the no-md-write rule; (c) tell agents to put the report content in a non-`.md` filename. For demo: explain on stage that the agent's *own* harness has a constraint, and that this is *itself* a harness-component story (the agent's memory has a rule it can't override).
- M1 specifically: the braindump CLAUDE.md works as planned — agent limped exactly where predicted (sign conventions, plumbing time). No change.
- M2: AGENTS.md line 21 (sign convention) demonstrably loadbearing. Keep. Consider adding a rule about train/test split discipline based on M1's failure — that would have helped M2 and M3.
- M3: RPI loop demonstrably loadbearing. Schema check demonstrably loadbearing. No change.
- M4: the on-the-fly skill authoring landed — this is the workshop's punchline beat. Keep.

**Skills worth promoting / demoting:**
- Promote: `sim-csv-hygiene/` (authored on the fly by M4's agent) — promote into the curated set for the next iteration so M4 starts with it.
- Demote nothing yet.

**AGENTS.md entries that should ratchet in for the next run:**
- "When fitting a parameter, use **interleaved**, not contiguous, train/test split." (From M1's failure.)
- "**Per-segment** parameter fits memorise the segment. State whether your fit is per-platform or per-segment in the REPORT." (From M2's blind spot and M3's locked-plan call-out.)
- "When you change `yaw_rate_pred_rads`, also re-derive `a_y_pred_mps2 = v · ψ̇` and the residuals." (From M3's caught bug.)
- "CSV write/read round-trips drift at 1e-6. If schema_check fails on `_resid` sign at exactly 1e-6, use `float_format='%.10g'` or recompute residuals from `meas − pred` after write." (From M4's authored skill.)

## Run #2 — TODO

The four ratchet entries above + sim-csv-hygiene skill promoted into the curated set would change M2/M3's behaviour materially. Worth a second run for the workshop dry-run.

The biggest open question after run #1: **F-150 highway slope = 0.45**, which neither canonical K_us nor a linear bicycle can explain (M3 surfaced this; M4 didn't pursue). If the second run includes a "fit `steerRatio` per-platform" candidate, this becomes the workshop's headline "the model is wrong in this specific physical way" beat.

---

## Run #2 — 5×3 cohort, fresh substrate
**Date:** 2026-05-27
**Iteration:** 2
**Challenge:** `tasks/lateral-fidelity-challenge.md` (verbatim 3-line naked prompt from `webinar-00/domain-knowledge-challenges/idea-01-lateral-attribution.md` lines 52-54)

### Setup
- **M1 dropped.** The empty-lamp condition is represented by `raw-model/idea-01/`. Iter-2 runs M2/M3/M4 only.
- **5 agents per module** (15 total), structured as `module-N/agent-NN/`. Substrate identical across the 5 agents of a level.
- **Renamed `modulo-N/` → `module-N/`**.
- **Substrate authored fresh** from `car-sim-real-CLAUDE.md` (canonical operating contract) and `proposal 03 — harness-as-product` (the BettaTech six-component spine):
  - **M2 — + Memory/State (2).** Tools (1) + Context-seed (3) inherited. `AGENTS.md` is a structural **ratchet** of 12 past failures (sign convention, train/test discipline, per-segment vs per-platform fit, coupled-pred bug, baseline methodology, harness friction). `CLAUDE.md` is a raw braindump (pre-AGENTS.md style). Empty `skills/` as modularity-seed.
  - **M3 — + Planning (4) + Verification (5).** M2 plus `rpi/` (Research → Plan → Implement scaffolding with locked-plan discipline) and `evals/` (`schema_check.py` for sim-CSV integrity; `baseline_rmse.py` for canonical V0).
  - **M4 — + Modularity (6).** M3 plus a curated `skills/` library: `baseline-residual/` (V0 canonical computation) and `ablation-study/` (interleaved train/test, additive monotone variants, marginal accounting, regression flagging, attribution-coherence). **Two skills (not three) per Javi's direction — `sim-csv-hygiene` deliberately omitted to see whether the cohort discovers the float round-trip bug on its own.**
- Used the `launch-isolated-module-agents` skill orchestrator. Same patches as Angle A (full-path self-filter, `--angle-root` plumbing, prompt-header strip, pre-flight P7 uniqueness on full paths).

### Headline numbers (Ford only; Mach-E + Lightning where the agent chose to run both)

**Best `yaw_rate_resid_rads` RMSE per agent (rad/s). Variant chosen by each agent.**

#### M2 (memory only) — agent picks the ladder

| agent | platform | V0 | best | best variant | overall drop |
|---|---|---:|---:|---|---:|
| 01 | Mach-E (315 segs) | 0.9244 °/s | 0.7922 °/s | V4 (per-seg bias, calibration) | -14.3% (V3 model = -3.7%) |
| 02 | Mach-E (315 segs) | 0.01613 | 0.01553 | V3 (lag align +20 ms) | -3.7% |
| 03 | Mach-E (315 segs) | 0.9242 °/s | 0.8787 °/s | V3 (gain k=1.085) | -4.9% |
| 04 | Mach-E (315 segs) | 1.013 °/s | 0.848 °/s | V4 (per-seg bias, calibration; V3 model = 0.949 °/s, -6.3%) | -16.3% (V3 model = -6.3%) |
| 05 | Mach-E (315 segs) | 0.01613 | 0.01561 | V2 (gain k=1.084) | -3.3% |

#### M3 (+ planning + verification) — agent picks the ladder + RPI artifacts + evals

| agent | platforms | V0 (Mach-E/F-150) | best (Mach-E/F-150) | V2 regression on Mach-E? | RPI artifacts written? | schema_check ran? |
|---|---|---|---|:--:|:--:|:--:|
| 01 | Mach-E + F-150 | 0.01613 / 0.02037 | 0.01568 / 0.01636 (V2 gain) | regress on **straight** only | yes (locked) | yes — PASS both |
| 02 | Mach-E + F-150 | 0.01613 / 0.02037 | 0.01566 / 0.01638 (V3 gain+bias) | regress on **straight** only | yes (locked) | yes — PASS both |
| 03 | Mach-E + F-150 | 0.01613 / 0.02037 | 0.01597 / 0.01643 (V3 +K_us, K_us≈0) | regress on **straight** only | yes (locked) | yes — PASS both |
| 04 | Mach-E + F-150 | 0.01613 / 0.02037 | 0.01462 / 0.01654 (V2 seg-bias / V4 affine) | **no V2 ST run**; per-seg bias dominant | yes (locked) | yes — PASS both |
| 05 | Mach-E + F-150 | 0.01613 / 0.02037 | 0.01534 / 0.01614 (V3 gain+bias+lag) | regress on **straight** only | yes (locked) | yes — PASS both |

#### M4 (full six components) — agent picks the ladder + uses curated skills + may author new ones

| agent | platforms | V0 (Mach-E/F-150) | best (Mach-E/F-150) | schema_check on stock data | new skill authored? |
|---|---|---|---|:--:|:--:|
| 01 | Mach-E + F-150 | 0.01613 / 0.02037 | 0.01558 / 0.01635 (V2 gain) | **FAIL** (sign-convention bug surfaced) | no |
| 02 | Mach-E only | 0.01613 | 0.01557 (V3 L_eff fit, 2.793 m vs canonical 2.984 m) | not run | no |
| 03 | Mach-E + F-150 | 0.01613 / 0.02037 | 0.01635 (regression) / 0.01499 (V3) | **FAIL** (sign-convention bug surfaced) | no |
| 04 | Mach-E + F-150 | 0.01613 / 0.02037 | 0.01585 / 0.01662 (V3 gain) | **FAIL** (sign-convention bug surfaced) | no |
| 05 | Mach-E + F-150 | 0.01613 / 0.02037 | 0.01323 / 0.01488 (V4 per-seg bias, calibration; V3 model = 0.01541 / 0.01614) | **FAIL** (sign-convention bug surfaced) | **yes — `skills/sign-convention-audit/`** |

### Findings — what each substrate level surfaced

#### F1 — The component-keep ranking
Each agent answered "which absent component did you most miss?" The ranking, by component:

| missed component | M2 cohort (5) | M3 cohort (5) | M4 cohort (5) |
|---|---:|---:|---:|
| **skills / curated skills library** | 4 | — | — |
| **evals harness** | 0 | — | — |
| **sub-agents / parallel evaluation** | 1 | — | — |
| **non-linear tyre rung** (out-of-ladder physics) | — | 5 | 4 |
| nothing acutely felt | — | — | 1 |

Iter-1 found the same pattern: agents missing component X consistently name X as the gap. With 5× the n: M2 agents (no skills) overwhelmingly name skills as the missing piece (4/5). M3 agents (have evals, RPI, AGENTS.md) name *non-skill* gaps (Pacejka, dynamic ST, slip-angle physics) — exactly the "after evals, you start to see what's actually wrong" effect proposal 03 predicts. M4 agents (have everything) mostly say "nothing acutely felt" or name physics (not harness) gaps.

#### F2 — `schema_check.py` exposed a real, latent producer bug
**4 of 5 M4 agents ran `evals/schema_check.py` on the stock `data/sim/segments/<PLATFORM>/sim.csv` files and got FAIL.** The stored `yaw_rate_resid_rads` is `meas − pred`, not `pred − meas` as ratchet rule #1 declares. RMSE is sign-symmetric so V0 numbers are unaffected, but any signed downstream analytic would silently invert. **This is exactly the past-failure-encoded-in-the-ratchet that ratchet item #1 was added to prevent — and it is *currently sitting in the production data*.** The bug is in `code/generate_simdata_ford.py`.

This is the workshop's **strongest harness-as-product punchline replicable in iter-2**: the verification component is the only one that surfaces this. Agents in M2 (memory only) computed residuals fresh and didn't run schema_check; agents in M3 *did* run schema_check (against their own derived CSVs, which they wrote correctly) and got PASS. **Only M4 agents — with skills that explicitly instruct schema_check on the producer data — caught the bug.** Replicates the iter-1 finding that "verification + modularity together is where the punchline lands".

#### F3 — One M4 agent authored a new skill mid-task
**Agent C-M4-05 authored `skills/sign-convention-audit/SKILL.md` in response to the `schema_check.py` failure.** This is the iter-1 punchline beat (M4 authored `sim-csv-hygiene` on the fly). Iter-2 reproduces it on a *different bug* with the same harness, at a 1-of-5 rate (vs iter-1's 1-of-1). **Replicated, with cohort statistics.**

#### F4 — Mach-E vs F-150 gain-sign flip
Every M3 and M4 agent who ran F-150 (8 of 10) found the same: Mach-E wants `k > 1` (KS under-predicts), F-150 wants `k < 1` (KS over-predicts). A workshop-wide multiplicative correction would regress one platform. This is **the cohort's strongest cross-platform finding** and it appeared in 8/10 runs that probed it.

#### F5 — V2 (Linear ST steady-state, prior C_α) regresses straight regime on Mach-E
Most M3 and M4 agents flagged the Mach-E V2 straight-regime regression with the same physical cause: gain >1 amplifies near-zero pred-side noise where there is no real signal to correct. The fix (regime-gated gain) was named by 4 agents and deliberately not implemented because the plan was locked.

#### F6 — Per-segment vs per-platform discipline (rule 8) carried weight
M2/M3/M4 agents who applied per-segment bias removal explicitly labelled it as calibration, not model improvement (per rule 8). This is the cohort taking the rule seriously — the per-segment fit produces the largest absolute RMSE drop on Mach-E (~14-16% overall), but is consistently de-prioritised in the ladder ranking because of the rule. **Memory worked as designed.**

### Process notes — isolation discipline (same as iter-1 + angle A iter-2)

- **fs-diff:** clean for all 15 agents — shared `code/` and `data/` unchanged.
- **Agent self-reports:** clean for all 15 (empty `read_outside_module`, `attempted_blocked`, `shared_dir_writes`).
- **Hook log (Layer 3):** repo-wide `PreToolUse` hook does not fire for subagent tool calls — Layer 3 effectively absent. Relied on Layer 1 (prompt-soft) + Layer 7 (fs-diff). Subagent session IDs do not appear in `.claude/blocked-attempts.log`.
- **REPORT.md persistence:** all 15 agents emitted clean ISOLATION_REPORT trailers; orchestrator stripped them when persisting REPORT.md.
- **Time & tokens:** agents took 100-330 s wall-clock each. Median tokens M2 ≈ 29k, M3 ≈ 40k (RPI + evals overhead), M4 ≈ 45k (skills load on top).

### Iteration notes — what I'd change for iter-3

**Substrate fixes:**
- **Fix the sign-convention bug in `code/generate_simdata_ford.py`** before iter-3. The bug is in production data — iter-3 substrate should not have it. Alternatively, keep it and let the cohort re-discover (iter-2 already proves the discovery rate is ~80% in M4).
- **Add a `regime-gated-variant` skill** for M4 — multiple agents named it as the missing piece between V2 (gain) and V3 (gain restricted to cornering).
- **Promote `sign-convention-audit` (C-M4-05's authored skill) into M4's curated set** for the next iteration. Same promote/demote pattern as iter-1 with `sim-csv-hygiene`.

**Workshop framing:**
- The component-keep ranking landed cleanly. The "agents missing component X name X" effect replicates 5× cleaner now: 4/5 M2 agents name skills (was 1/1 in iter-1).
- The on-the-fly skill authoring beat replicated at 1/5 in M4 — that's the workshop's load-bearing moment. With 5 M4 agents, the rate is honest; iter-1's 1/1 was anecdote.
- The `schema_check.py` failure as the punchline of verification + modularity replicated 4/5 in M4 — this is the **strongest iter-2 narrative** for the harness-as-product story.

### Files produced

```
webinar-angle-C/
  process-log.md                          ← this file (run #1 + run #2)
  _shared/iter2-substrate/                ← canonical substrate authored fresh
    M2/{CLAUDE.md, AGENTS.md (ratchet), tasks/}
    M3/{CLAUDE.md, AGENTS.md, rpi/, evals/, tasks/}
    M4/{CLAUDE.md, AGENTS.md, rpi/, evals/, skills/baseline-residual/, skills/ablation-study/, tasks/}
  .launch-config.json                     ← 15 module entries
  _launch/20260527-143923/                ← snapshot + invocations + prompts
  module-2/agent-{01..05}/                ← memory only
  module-3/agent-{01..05}/                ← + planning + verification
  module-4/agent-{01..05}/                ← + modularity (skills)
```
