
---

# RUN-LOG iter 2 — 5×3 cohort, empathy angle, fresh substrate
date: 2026-05-27
iteration: 2
challenge: tasks/lateral-fidelity-challenge.md (verbatim 3-line naked prompt from `webinar-00/domain-knowledge-challenges/idea-01-lateral-attribution.md` lines 52-54)
launch_id: webinar-angle-B/20260527-143923 (approx)

## What changed from iter 1

- **M1 dropped.** The empty-lamp condition is now represented by `raw-model/idea-01/`. Iter-2 re-runs M2/M3/M4 to study the context-cost axis proper.
- **5 agents per module** (15 total), structured as `module-N/agent-NN/`. Substrate identical across the 5 agents of a module level.
- **Renamed `modulo-N/` → `module-N/`**.
- **Substrate authored fresh** from the operating contract material in `car-sim-real-CLAUDE.md` and `proposal 02 — context-engineering-empathy`. The angle's lever is **context cost per turn**, not artifact accretion:
  - **M2 — bloated.** Single ~10KB `AGENTS.md` containing full vehicle-dynamics conventions, operating contract, CSV schema, parameters, traps. Plus a `CLAUDE.md` re-dumping workspace layout and contract. Everything paid every turn.
  - **M3 — progressive disclosure.** Lean `AGENTS.md` (~30 lines, pointers only). Two on-demand skills: `sim-real-runtime/` (operating contract + truth matrix + CSV schema + traps) and `vehicle-dynamics-rlog/` (ISO 8855 sign conventions + units + fidelity ladder + variant discipline). Metadata-first; bodies load only when invoked.
  - **M4 — progressive disclosure + RPI.** M3 + `rpi/templates/{research,plan,implement-notes}.md` + `rpi/README.md` instructing the agent to break work across three explicit phases with a locked plan.
- **Naked prompt verbatim** from `idea-01-lateral-attribution.md` lines 52-54.
- **Inspector skipped for the live render** (per Javi). Per-agent token usage captured from each `<task-notification>`'s `<usage>` field.

## Token-cost cohort (the empathy beat)

Per-agent `total_tokens` from the run notifications, by module:

| module | agent-01 | agent-02 | agent-03 | agent-04 | agent-05 | mean | median |
|---|---:|---:|---:|---:|---:|---:|---:|
| M2 (bloated) | 35 411 | 37 300 | 36 480 | 29 210 | 28 929 | 33 466 | 35 411 |
| M3 (lean+skills) | 29 352 | 38 400 | 33 926 | 37 693 | 40 931 | 36 060 | 37 693 |
| M4 (lean+skills+RPI) | 48 359 | 48 013 | 49 340 | 58 216 | 46 833 | 50 152 | 48 359 |

**Cohort empathy finding (counter-intuitive).** M3 was not consistently cheaper per turn than M2 in this single-shot run, and M4 was the most expensive of the three. The token deltas the empathy angle wants to surface — 944-vs-53 per turn for AGENTS.md bloat vs skill metadata — are *long-session* effects (the 30%-cliff / 40%-cliff curve), and a 4-7 min agent run with one or two skill loads does not realise them. M2's bloated AGENTS.md is paid every turn but the run is short enough that M3's skill-body loads (when actually invoked) more than compensate. **M4 confirms the iter-1 finding**: RPI imposes a real, measurable per-run overhead (~13-25k extra tokens for the same task, the cost of the three artifact files plus the locked-plan discipline). On a short single-shot task that is a tax, not a benefit; the benefit lives in multi-iteration projects where the artifacts compose. This replicates iter-1's "RPI shifts the variance, not the mean" finding with 5× the n.

## RMSE cohort (Ford Mach-E, agent-chosen segment counts)

All agents on Mach-E except where noted. Agent-chosen segment counts and regime masks differ between agents, so cell-to-cell comparison is approximate. The shape is the headline, not the absolute number.

### M2 — bloated AGENTS.md + CLAUDE.md dump

| agent | V0 | V1 (bias) | V2 / next | V3 / further | V4 / further | best_var | best_RMSE | overall_drop | V2/ST flagged regression? |
|---|---:|---:|---:|---:|---:|---|---:|---:|:--:|
| 01 (Mach-E + Lightning) | 0.01316 / 0.01584 | 0.01073 / 0.01416 | 0.01044 (lag) / 0.01395 (lag) | 0.01157 (ST regr) / 0.00792 | — | M2 V2 / Light V3 | 0.01044 / 0.00792 | -21% / -50% | n/a (different ladder) |
| 02 (Mach-E, 80) | 0.01190 | 0.00992 (bias) | 0.01145 (ST prior, regr) | 0.00924 (lag) | 0.00864 (+ gain) | V4 | 0.00864 | -27.4% | **yes** |
| 03 (Mach-E, 315) | 0.01613 | 0.01414 (bias) | 0.01475 (ST prior, regr) | 0.01432 (ST fit) | 0.01420 (K_us fit) | V4 | 0.01420 | -11.9% | **yes** |
| 04 (Mach-E, 315) | 0.01613 | 0.01461 (bias) | 0.01388 (gain K*=1.09) | 0.01439 (speed-dep regr) | — | V2 | 0.01388 | -14.0% | n/a |
| 05 (Mach-E, 305) | 0.01161 | 0.00891 (bias) | 0.00782 (K_us) | 0.00714 (lag) | — | V3 | 0.00714 | -38.5% | n/a |

### M3 — lean AGENTS.md + on-demand skills

| agent | V0 | V1 (bias) | V2 (ST prior) | V3 (ST fit) | V4 (LOSO ML) | best_RMSE | overall_drop | V2 flagged as regression? |
|---|---:|---:|---:|---:|---:|---:|---:|:--:|
| 01 (Mach-E, 315) | 0.01613 | 0.01469 | 0.01551 | 0.01551 (fit returns x0) | 0.01530 | 0.01469 (V1) | -8.9% | **yes** |
| 02 (Mach-E, 315) | 0.0161  | 0.0147  | 0.0155  | 0.0151 (C_α softer than prior) | 0.0149 | 0.0149 | -7.5% | **yes** |
| 03 (Mach-E, 120) | 0.01550 | 0.01429 | 0.01570 | 0.01536 (C_α pegged) | 0.01251 | 0.01251 (V4) | -19.3% | **yes** |
| 04 (Mach-E, 120) | 0.01326 | 0.01098 | 0.01398 | 0.01192 (C_αr pegged) | — | 0.01098 (V1) | -17.2% | **yes** |
| 05 (Mach-E, 306) | 0.01316 | 0.01105 | 0.01225 | 0.01166 (C_α=400k, ~half prior) | — | 0.01105 (V1) | -16.0% | **yes** |

### M4 — lean AGENTS.md + skills + RPI

| agent | V0 | V1 (bias) | V2 (ST prior) | V3 (ST fit) | V4 (lag / ML) | best_RMSE | overall_drop | V2 flagged as regression? |
|---|---:|---:|---:|---:|---:|---:|---:|:--:|
| 01 (Mach-E, 60) | 0.01214 | 0.01055 | 0.01248 | 0.01550 (C_α pegged low) | 0.01336 (Ridge LOSO) | 0.01055 (V1) | -13.1% | **yes** |
| 02 (Mach-E, 315) | 0.01613 | 0.01469 | 0.01551 | 0.01515 | — | 0.01469 (V1) | -8.9% | **yes** |
| 03 (Mach-E, 80) | 0.01451 | 0.01262 | 0.02035 | 0.02188 (C_αf upper) | 0.02143 (Ridge LOSO) | 0.01262 (V1) | -13.0% | **yes** |
| 04 (Mach-E, 315) | 0.01613 | 0.02010 (bias regress) | 0.01550 | 0.01550 (fit returns priors) | 0.01533 (lag) | 0.01533 (V4) | -4.96% | n/a (different ladder) |
| 05 (Mach-E, 80) | 0.01190 | 0.01013 | 0.01656 | 0.01656 (flat fit) | 0.01656 | 0.01013 (V1) | -14.9% | **yes** |

## Key cross-cohort findings

### Finding 1 — The empathy beat does not land in a single short run

This is the **headline calibration finding** for angle B. Iter-1 already flagged it; iter-2 with 5× the n confirms: a 4-7 min agent run does not cross the 40% context-fill cliff. M3 is not consistently cheaper than M2 *on this task*; M4 is the most expensive (RPI overhead). The empathy story needs either:
- a deliberately long multi-turn task, or
- the inspector running so the *per-turn cost gradient* is visible even when the cliff isn't hit.

The current state is: M2 vs M3 is a wash; M4 is +50% tokens for ~the same task quality. **Bring the inspector live or extend the task to multi-turn before staging.**

### Finding 2 — V2 (Linear ST + openpilot prior C_α) regression is universally reproduced

11 of 13 agents on Mach-E who climbed past V1 flagged V2 as a regression with the same physical cause: openpilot's prior `C_α` is calibrated for production lateral planning, not for residual minimisation; on these tyres at moderate `|a_y|` the linear-ST steady-state gain *over-rotates* or *under-rotates* depending on the agent's variant ordering, and never beats KS+bias. **This is the same headline finding as angle A iter 2 (10/10 M3+M4 agents).** Reproducible across angles, datasets, and substrate flavours.

### Finding 3 — V3 `C_α` fit produces three distinct failure modes

Across the cohort:
- Some agents' fits returned **exactly the prior** (loss surface flat at x0; 3 cases).
- Some agents' fits **pegged the upper bound** at 500 kN/rad (linear-ST form mis-specified; 3 cases).
- Some agents' fits returned **substantially softer stiffnesses than the prior** (e.g. 155 kN/rad rear vs 356 kN/rad prior; 2 cases).
- Some agents' fits **pegged the lower bound** (50 kN/rad; 1 case — M4-agent-01).

These contradict each other — the cohort *itself* is a probe of the loss-surface geometry, and the answer is "it depends on the agent's optimizer setup". This is workshop-relevant: it shows that the same skill-prescribed procedure produces different conclusions depending on solver choice. **Iter-3 ratchet candidate: prescribe a specific multi-start strategy in the skill.**

### Finding 4 — The cross-platform gain-sign flip

One agent (B-M2-01) ran both Fords. On Mach-E `k = 1.07`, on F-150 `k = 0.83` — opposite signs of correction. Other agents who ran only Mach-E found the same `k ≈ 1.07-1.09`. **A workshop-wide multiplicative correction would regress one platform** — confirming the iter-1 hypothesis that per-platform fits are mandatory.

### Finding 5 — Per-segment yaw-gyro bias is the cheapest legitimate win

13 of 15 agents found V1 (per-segment yaw-gyro bias removal) to be a real win on Mach-E, accounting for the bulk of the V0→V_best drop — typically halving straight-regime RMSE. Two agents (M4-04, M2-01-bias-fold-trap) found V1 regressed because they conflated cornering-bias-leakage onto straights. **The cheap fix wins; the model upgrade ladder is mostly a regression study.**

## Process notes — isolation discipline

- **fs-diff:** clean for all 15 agents — shared `code/` and `data/` unchanged.
- **Agent self-reports:** clean (empty `read_outside_module`, `attempted_blocked`, `shared_dir_writes` for all 15). Several agents named temptations they resisted (peeking at sibling agents, reading `_shared` or `webinar-00`).
- **Hook log (Layer 3):** same finding as angle A iter 2 — the repo-wide `PreToolUse` hook does not fire for subagent tool calls in this environment. Layer 3 was effectively absent for this run. Relied on Layer 1 (prompt-soft) + Layer 7 (fs-diff).
- **REPORT.md persistence:** all 15 agents emitted clean `ISOLATION_REPORT:` trailers in their text responses (captured here). The parent stripped them when persisting `REPORT.md` (verifier V1 would FAIL on shape, as in angle A — same root cause: the orchestrator strips the trailer for a cleaner deliverable).
- **Time & tokens:** agents took 100-330 s wall-clock each. M2 cohort median ~140 s; M3 cohort median ~180 s; M4 cohort median ~220 s (RPI overhead).

## Iter-3 punch list

- [ ] **Bring the inspector live or extend the task to multi-turn.** Single-shot 4-7 min runs do not cross the 40% cliff; M2 vs M3 token deltas are not separable in a single run.
- [ ] **Pre-fix the `yaw_rate_resid_rads` sign-convention bug** in `code/generate_simdata_ford.py`. Five agents (C-M3-05, C-M4-01, C-M4-03, C-M4-04, C-M4-05) independently discovered that the stored column is `meas − pred`, not `pred − meas` as the ratchet declares. Fix at the producer; iter-3 substrate should NOT have the bug.
- [ ] **Prescribe multi-start C_α fit in the skill.** Three solver-induced failure modes appeared; a specified strategy would converge the cohort.
- [ ] **Tighten the M2 narrative.** "M2 = bloated context that crushes performance" did not land empirically — M2 agents matched or beat M3 on RMSE in some runs. The honest framing is "M2 carries token-cost per turn, which scales with session length, not single-shot performance." Lock this in the proposal text before staging.

## Files produced

```
webinar-angle-B/
  RUN-LOG.md                              ← this file (iter-1 + iter-2)
  _observations/                          ← iter-1 retrospective; not loaded
  _shared/iter2-substrate/                ← canonical substrate authored fresh
    M2/{AGENTS.md, CLAUDE.md, tasks/}
    M3/{AGENTS.md, skills/sim-real-runtime/, skills/vehicle-dynamics-rlog/, tasks/}
    M4/{AGENTS.md, skills/..., rpi/{README.md, templates/}, tasks/}
  .launch-config.json                     ← 15 module entries
  _launch/20260527-143923/                ← snapshot + invocations + prompts
  module-2/agent-{01..05}/                ← bloated harness
  module-3/agent-{01..05}/                ← progressive disclosure
  module-4/agent-{01..05}/                ← + RPI
```
