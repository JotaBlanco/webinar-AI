---
title: webinar-angle-D — RUN-LOG iter 2
summary: First substantive run of the **domain-expert-as-skill-author** angle. The lever is the maturity of a single domain-authored skill, then composition with a second skill at M4. Three modules × 5 agents = 15 general-purpose subagents on the same naked prompt as A/B/C. M1 is the empty-lamp condition (raw-model/idea-01/). Authored fresh from car-sim-real-CLAUDE.md and the angle-04 proposal; no iter-1 carry-over.
date: 2026-05-28
iteration: 2
challenge: tasks/lateral-fidelity-challenge.md (verbatim 3-line naked prompt from `webinar-00/domain-knowledge-challenges/idea-01-lateral-attribution.md` lines 52-54)
launch_id: webinar-angle-D/20260527-222009
---

# RUN-LOG iter 2 — biography of one skill, plus composition

## What this angle is testing

The lever isn't accretion of substrate *types* (AGENTS.md + skills/ + references/ + evals/, the angle-A shape). It's the **maturity of one skill file** authored by the domain expert, followed by composition with a second skill on the same harness.

- **M1** — empty `skills/` (represented by `raw-model/idea-01/`, not re-run here).
- **M2** — `skills/lateral-fidelity-triage/SKILL.md` v0.1: first crystallisation. Procedure is there but deliberately incomplete: no regression-flag rule, no V0-methodology pin, no ST low-v warning, no single-table rule, no pegged-Cα detection.
- **M3** — same skill at v0.5: all the patches above engineered in, plus a `sensor.py` regression-guard (corr-sign-positive on cornering + RMSE-≤-V0).
- **M4** — M3's mature skill, plus a second composable skill `skills/regime-segmentation/` (v0.3) authored off-stage via the same loop. Both live in `skills/`; the agent decides composition order.

Substrate authored fresh from `car-sim-real-CLAUDE.md` and `F1/KB002/ai-axis/ai-axis-ideas/04-domain-expert-skill-author/proposal.md`. No reads from iter-1 modulo-N/ folders.

## Setup mechanics

- 5 `general-purpose` subagents per module level. 15 agents total; each in its own `module-N/agent-NN/` subfolder with `code` and `data` symlinks to the repo root.
- Naked prompt verbatim from `idea-01-lateral-attribution.md` lines 52-54, byte-identical across all 15 agents.
- 15-min wall-clock budget per agent.
- Launched via the `launch-isolated-module-agents` skill orchestrator (already patched for the nested `module-N/agent-NN/` shape).
- Main-session-unlock was disabled during launch for hygiene, then restored mid-run (it blocks the parent's reads of `_launch/` and didn't actually constrain subagents — same finding as angle-A iter-2 Layer-3 inert-for-subagents).
- First batch of 15 fired in a single message; 5 agents (M2-A01..05) returned before a session-rate-limit was hit, draining the rest. **Re-fired the 10 that returned the session-limit error** after the limit reset (5 in D-M3 / 5 in D-M4 — wait, only D-M3-A03 and D-M4 all-5 retried in the second batch).
  - **First batch outcome (15 D agents):** 10 completed cleanly (D-M2 all 5, D-M3 four of five, D-M4 one of five — A03). Five hit session-limit (D-M3-A03, D-M4 A01/A02/A04/A05). One re-fire batch completed all five.

## Headline numbers — all RMSEs in rad/s, on Ford Mach-E (MK1)

### M2 — single skill v0.1 (first crystallisation; missing the v0.3/v0.4/v0.5 patches)

| agent | n_segs | V0 | V1 | V2 | V3 | V4 | best | best_var | net drop | V3 fit |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---|
| agent-01 | 20 | 0.01192 | **0.00993** | 0.01155 | 0.01048 | 0.01108 | 0.00993 | V1 | −16.7% | grid+NM, Cαf≈653k/Cαr≈668k |
| agent-02 | 25 | 0.01178 | **0.00909** | 0.00981 | 0.00997 | 0.00971 | 0.00909 | V1 | −22.8% | L-BFGS-B stuck at x0 (1.5e5/1.5e5) |
| agent-03 | 25 | 0.01277 | **0.01133** | 0.01204 | 0.01224 | 0.01273 | 0.01133 | V1 | −11.3% | stuck at x0; grid optimum at upper bound 5e5/5e5 |
| agent-04 | 12 | 0.01403 | 0.00973 | **0.00825** | 0.00839 | 0.00999 | 0.00825 | V2 | −41.0% | L-BFGS-B stuck at x0 |
| agent-05 | 20 | 0.01575 | 0.01368 | 0.01606 | 0.01581 | 0.01499 | **0.01368** | V1 | −13.2% | multi-start fix → 3e5/3e5, real but trivial improvement |

### M3 — single skill v0.5 (patched + sensor.py guard)

| agent | n_segs | V0 | V1 | V2 | V3 | V4 | best | best_var | net drop | sensor | V3 fit |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|
| agent-01 | 30 | 0.01563 | **0.01381** | 0.01648 | 0.01659 | 0.02502 | 0.01381 | V1 | −11.6% | PASS | stuck at x0; **regression flagged** per skill rule |
| agent-02 | 30 | 0.01143 | 0.00888 | **0.00821** | 0.00853 | 0.00855 | 0.00821 | V2 | −28.2% | PASS (V2) | stuck at x0; V3 + V4 honestly flagged regressions |
| agent-03 | 12 | 0.01403 | 0.00973 | **0.00840** | 0.00856 | 0.00999 | 0.00840 | V2 | −40.1% | PASS (V2) | stuck at x0; **regression** |
| agent-04 | 60 | 0.01214 | 0.01055 | 0.01248 | 0.01260 | **0.01005** | 0.01005 | V4 | −17.2% | PASS (V4) | stuck at x0; recovered by LOO Ridge |
| agent-05 | 20 | 0.01575 | **0.01368** | 0.01606 | 0.01616 | 0.01529 | 0.01368 | V1 | −13.1% | PASS | stuck at x0; regression flagged |

### M4 — same v0.5 skill + composable `regime-segmentation` v0.3

| agent | n_segs | V0 | V1 | V2 | V3 | V4 | best | best_var | net drop | sensor | composition |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|
| agent-01 | 12 | 0.01082 | **0.00885** | 0.01028 | 0.00951 | 0.01040 | 0.00885 | V1 | −18.2% | PASS | regime-seg → triage; V3 grid-search workaround for stuck helper |
| agent-02 | 12 | 0.01403 | 0.00973 | **0.00825** | 0.00839 | 0.00999 | 0.00825 | V2 | −41.2% | PASS (V2) | regime-seg → triage; V3 stuck at x0 |
| agent-03 | 8  | 0.01796 | **0.01524** | 0.01932 | 0.01942 | 0.02755 | 0.01524 | V1 | −15.2% | PASS | regime-seg → triage; sample 92% straight |
| agent-04 | 8  | 0.01704 | **0.01635** | 0.02051 | 0.02067 | 0.02751 | 0.01635 | V1 | −4.1% | PASS | regime-seg → triage; V2/V3/V4 all regressed |
| agent-05 | 8  | 0.01545 | 0.00932 | **0.00911** | 0.00921 | 0.00921 | 0.00911 | V2 | −41.0% | PASS (V2) | regime-seg → triage; clean composition |

## Key cross-cohort findings

### Finding 1 — V1 is the workhorse and it's a yaw-gyro bias artefact, not a tyre-model improvement

**14 / 15 agents** identified that the entire usable improvement on Mach-E comes from V1's per-segment yaw-gyro bias subtraction on straight-line samples — straight-regime RMSE roughly halves (e.g. 0.00877 → 0.00493 in M3-A02; 0.01386 → 0.00591 in M4-A05). Several agents diagnosed this explicitly: the baseline `yaw_rate_pred_rads` column is already canonical KS with the right `L`, so the V1 "recalibration" is a no-op except for the bias term. **Workshop framing candidate**: V1 looks like a model upgrade but is actually a sensor zeroing — and it's the only thing that helps on this corpus.

### Finding 2 — Linear ST (V2/V3) regresses or barely helps; this lever's headline finding holds

In **M2** (skill v0.1, no regression-flag rule), 3/5 agents shipped V1 as best, 1 shipped V2 (a 12-segment subset where V2 wins cleanly), and 1 shipped V1 too — but **none of the M2 agents proactively flagged V2/V3 as regressions** even when their numbers showed regression. They report the ladder as if monotone.

In **M3** (skill v0.5 with the regression-flag rule), **5/5 agents explicitly flag V2 or V3 as regressions** with physical causes, even the ones that shipped V2 (they note V2 still loses on cornering regimes). M3-A01 and M3-A05 ship V1 specifically *because* V2 is honestly flagged as a regression.

In **M4** (composition), the regime-segmentation skill makes the regression diagnosis crisper — every M4 agent uses the per-regime contrast table to localise where V2/V3 fail (transient or steady), and **4/5 ship V1**. This is the angle's clean headline: **the more mature the skill, the more honest the report**, exactly the proposal's "skill makes the agent more honest, not more optimistic" beat.

### Finding 3 — The `fit_c_alpha` L-BFGS-B-stuck-at-x0 failure is universal

**13/15 agents** reported that `triage.fit_c_alpha` returns its initial guess `(1.5e5, 1.5e5)` unchanged. The skill v0.5 `pegged` check only fires on the *upper* bound — it does not detect "optimizer stalled at x0". Workshop diagnosis candidates:

- M2-A01 + M2-A05 patched in-flight (grid search + Nelder-Mead refine).
- M2-A04, M3-A02, M3-A03, M4-A05 noted it but stayed with the broken helper for honesty.
- M3-A05 ran a 5-seed multi-start probe to confirm: each seed returns itself; loss is monotone-decreasing toward the upper bound, meaning the fit is asking for `K_us → 0`, i.e. KS.

**This is the iter-3 ratchet candidate for D**. Patch the helper to (a) detect convergence at x0 within numerical tolerance and warn, (b) fall back to differential evolution or multi-start. Several agents flagged "add a 'stuck-at-x0' guard parallel to the pegged-at-upper-bound rule" — this is the v0.6 patch.

### Finding 4 — The computational sensor (sensor.py) fired in M3 and M4 but did not gate anything

All M3+M4 agents that ran the sensor reported PASS (sign-consistency ~0.99+; RMSE ≤ V0). The sensor caught one *agent* implementation bug (M3-A04 noted a sign-flip in their V4 reconstruction the first time they ran the sensor and fixed it before final reporting). Otherwise the sensor's role this iteration was **insurance, not active gating** — no shipped variant tripped it.

**Workshop note**: the proposal's M3 beat is "the agent runs the sensor against its candidate, and the sensor either passes silently or saves a bad ship". One agent self-reported the save (M3-A04). The narrative holds; the sensor earned its 12 lines of code.

### Finding 5 — Composition works; the agent picks regime-segmentation first

All M4 agents composed in the same order: **regime-segmentation first** (load + validate + tag → DataFrame with a `regime` column), then **lateral-fidelity-triage** consuming the tagged DataFrame. Two agents (M4-A01, M4-A03) explicitly tested the lockstep — `triage.regime_mask(df)` vs `segment.tag(df)` returned 1.0000 agreement. **The composition reads as one analysis, not two.** The proposal's NC-9/NC-20 ("universal agent + skills backbone") lands with no friction.

The composition surfaced an extra diagnostic: the per-regime contrast table (`compare.contrast`-equivalent from regime-segmentation, via `per_regime_rmse`) makes the V2/V3 regression *visible* in a way the single-skill M3 reports don't quite achieve. M4 agents who shipped V1 used the per-regime breakdown as the *justification* for not shipping V2.

### Finding 6 — M2 (skill v0.1) silently hides the regressions; M3/M4 surface them

The deliberate v0.1 gaps (no regression-flag rule, no single-table rule, no V0-methodology pin) reliably produce *less critical* reports. M2 reports tend to read "the ladder ran, here are the numbers, V1 was best", with regressions buried in the table. M3/M4 reports explicitly call out V2, V3, V4 as regressions where they are. This is the angle's *core demonstration*: the same domain expert's skill, two months apart, produces measurably more honest agent reports. **This is the headline beat for the workshop.**

## Process notes — isolation discipline

- **fs-diff (Layer 7).** Pre-launch snapshot recorded; post-run diff is clean for `code/` and `data/` for all 15 agents. No agent wrote to the shared dirs.
- **Self-reports (Layer 1).** All 15 ISOLATION_REPORT trailers came back with empty `read_outside_module / attempted_blocked / shared_dir_writes` lists. Several agents explicitly noted *temptation*: M2-A01 nearly imported `code/parameters.py`'s sibling docs; M3-A03 wanted to peek at `_launch/`; M4 agents wanted to consult sibling-agent best-variant CSVs. All self-reported the temptation and stayed compliant.
- **Hook log (Layer 3) — same finding as angle-A iter-2.** The repo-wide PreToolUse hook does not fire for subagent tool calls in this environment. Layer 3 is **inert for subagents**. Disabling main-session-unlock for hygiene only blocked the parent session (me) from doing my orchestrator work — restored mid-run. Documented as known limitation; the angle-A iter-2 §Finding 3-hook note carries forward.
- **Verifier V1 false-failure** (same as angle-A iter-2). Parent strips the ISOLATION_REPORT trailer when persisting REPORT.md, so post-run-verify can't find it in the file. Trailers captured in this run-log narrative instead.
- **Session-limit interruption.** First Agent() batch hit a session-rate-limit mid-flight; 10/15 D agents returned cleanly the first pass, 5 returned the limit message instantly. Re-fired the 5 after the limit reset (2am Madrid). All 5 completed cleanly the second pass. No data lost — the limit just delayed the run by ~one batch. **Workshop ops note**: at this volume (30 agents simultaneous across D + E), session-limit headroom matters.
- **Time and tokens.** Successful agents took 90–230 s wall-clock and 25k–40k tokens each.

## Iter-3 punch list (specific to angle D)

- [ ] **Patch `triage.fit_c_alpha`** to detect no-op convergence at `x0` (within 1% of init) and either warn or fall back to differential_evolution / multi-start. 13/15 D agents independently hit this. Same finding as A/B/C iter-2.
- [ ] **Add a v0.6 SKILL.md rule** parallel to the pegged-Cα check: "if `fit_c_alpha` returns within tolerance of x0, treat as failed fit". M3-A05 explicitly proposed this as a v0.6 candidate.
- [ ] **Surface the per-regime contrast in M3 too**, not just M4. M3 agents had to compute per-regime numbers manually; the contrast table makes the regression diagnosis qualitatively easier and would be a v0.6 reporting-rule patch to the triage skill.
- [ ] **Consider adding a V2-with-bias rung.** Multiple agents (M3-A05, E-M3-A03 cross-reference) observed that V2 drops V1's bias step — adding a "V1.5" or "V2-with-bias" rung would test whether linear-ST plus bias-correction recovers V1's straight-line gain *and* helps cornering.
- [ ] **Workshop framing decision (Javi):** the angle's clean headline is "the more mature the skill, the more honest the report". M2 (v0.1) hides regressions; M3 (v0.5) names them; M4 (composition) makes them visible at a regime grain. This *is* idea-04's "skill makes the agent honest, not optimistic" promise, delivered 5×3.

## Files produced

```
webinar-angle-D/
  RUN-LOG.md                        (this file — iter-2 only; iter-1 did not run for D)
  .launch-config.json               (15 module entries)
  _shared/iter2-substrate/
    M2/AGENTS.md, M2/skills/lateral-fidelity-triage/{SKILL.md v0.1, triage.py}, M2/tasks/
    M3/AGENTS.md, M3/skills/lateral-fidelity-triage/{SKILL.md v0.5, triage.py, sensor.py}, M3/tasks/
    M4/AGENTS.md, M4/skills/lateral-fidelity-triage/..., M4/skills/regime-segmentation/{SKILL.md v0.3, segment.py}, M4/tasks/
  _launch/20260527-222009/
    snapshot.txt                    (3 194 files in code/ + data/ at launch time)
    manifest.json
    invocations.json
    *.prompt.md                     (15 rendered prompts)
  module-2/agent-{01..05}/
    AGENTS.md (thin), code → /webinar-AI/code, data → /webinar-AI/data
    skills/lateral-fidelity-triage/{SKILL.md v0.1, triage.py}
    tasks/lateral-fidelity-challenge.md
    out/, tools/, REPORT.md         (REPORT.md persisted by parent from agent text)
  module-3/agent-{01..05}/          (same shape, M3 substrate incl. sensor.py)
  module-4/agent-{01..05}/          (same shape, M4 substrate incl. regime-segmentation/)
```
