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
