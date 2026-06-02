---
title: m4-cohort-findings
description: Evidence-backed findings from the m3.v3 cohort (10 agents, run 20260601-173918). Citable, transferable patterns the m4 critique-residuals router and iterate gate use as cohort precedent. Each finding is a concrete fact about *this* dataset, not generic ML advice.
when-to-load: At the start of a fresh m4 session, before deciding which structural attack to try. Critique-residuals references this doc by section number when emitting cohort-evidenced routes. Also load when interpreting an unexpected gate output — a finding here may explain why.
load-cost: ~1000 words.
updated: 2026-06-02
---

# m4 cohort findings — m3.v3, 10 agents, what actually happened

These eight findings are extracted from `module-3.v3/agent-{01..10}/REPORT.md`
and the latest cohort grade (`_grade/20260601-173918/cohort.md`). Every finding
cites the specific agent and file. The router and gate use these by section
number — when you see `cohort_precedent: §N`, this is what N points at.

## §0 — Headline: the four evidence-backed moves

Read this section first. Each is expanded below with citations.

1. **Per-platform additive bias correction** (§2) → +3.7-4.6% CTE, zero structural cost.
2. **Orthogonal residual learner head on V1** (§4) → +1-5% CTE, reliably won across every cohort agent that tried it (03, 04, 06, 08, 10). agent-03 shipped this for −30% yaw / −21% CTE — the m3.v3 cohort winner.
3. **Rung-1 dynamic ST WITH fit C_αf, C_αr, Iz** (§1, §7) — *never demonstrated by the cohort* because every attempt used carParams values. `_shared/rung1_starter.py` is the scaffold that exists specifically to close this gap. Higher-risk path.
4. **k-fold route-grouped CV on every candidate** (§6) — agent-07 cohort failure mode (asymmetric-bias subset fit flipped Lightning sign) is what motivates this discipline.

**Orthogonal is a peer of rung-1**, not a fallback. The historically-winning
pair on this dataset is `(per-platform bias correction) + (residual-learner head)`.
Choose rung-1 over orthogonal only if your residual diagnosis identifies a
transient-dynamics signature a residual learner cannot capture.

Avoid: linear steering-rate feedforward (§3), lag-τ refitting (§8),
single-subset fits (§6).

---

## §1 — All rung-1 dynamic single-track attempts failed or were abandoned

Agents 01, 03, 04, 05, 06 attempted (or planned) rung-1 linear-dynamic ST with
slip angles. Common failure mode: **under-parameterization when using
carParams-derived `C_α` and `Iz` instead of fitting them.** Agent-06 confirmed
the failure predicted in `dynamics-formulations.md`: rung-0 with per-platform
fit beat rung-1 by **+11% yaw RMSE** when the rung-1 used carParams values
instead of fitted ones. Agent-03's dyn-ST optimizer could not converge on
IONIQ (84 routes, 2.3M rows) in the 45-minute budget — a time-budget failure,
not a structural-impossibility one.

**Cite:** `module-3.v3/agent-06/REPORT.md:21-22`, `agent-03/REPORT.md:18`.

**M4 implication:** `_shared/rung1_starter.py` exists specifically to remove
the integration-stability and fit-loop overhead. Critique-residuals emits
`climb_to_rung_1` with `confidence: low` precisely because of this evidence —
the route is technically possible but practically blocked by the under-param
+ budget pattern.

---

## §2 — Signed bias (not RMS noise) dominates CTE on Mach-E and IONIQ-5

V1 carries persistent per-platform yaw-rate biases:
- **Mach-E**: −0.00142 rad/s → −22 m CTE drift
- **IONIQ-5**: −0.00075 rad/s → −12 m CTE drift
- **Lightning**: at noise floor; per-platform bias correction adds nothing.

A single additive constant per platform recovers **+3.7 to +4.6% pooled CTE**
with **zero structural change**. Agents 01, 05, 07, 09, 10 all shipped this;
all matched or beat the structurally-novel approaches that ignored bias first.

**Cite:** `module-3.v3/agent-01/REPORT.md:14-17`, `agent-05/REPORT.md:13`,
`agent-07/REPORT.md:10-16`.

**M4 implication:** This is the new highest-leverage move on this dataset
(replacing per-segment δ₀, which is now baked into V1). The router emits
`try_per_platform_bias_correction` with `confidence: high` when the residual
verdict surfaces `structure_detected:signed_bias` on either platform.

---

## §3 — Steering-rate feedforward (linear `dδ/dt` terms) fails

Agents 01, 03 (lead-compensator), 05 (`k_dd`), 07 (steer-rate-FF) all tried
linear steering-rate residual corrections. Result: agent-03's lead-compensator
optimiser drove `K_d` negative and `tau → 0.01` (the optimiser was trying to
*remove* V1's lag, not extend it); agent-05's `k_dd` term matched zero within
noise.

Conclusion (agent-05): "V1's first-order lag with τ≈0.07 s is doing nearly
all the work an input-only linear correction in steering-rate could plausibly
do. The remaining transient residual needs a model with internal dynamics
state."

**Cite:** `module-3.v3/agent-03/REPORT.md:36`, `agent-05/REPORT.md:81-84`.

**M4 implication:** The router emits `drop_lever_<param>` when the fit shows
collapse on steering-rate terms — this is now the cohort-evidenced default,
not a maybe.

---

## §4 — Residual-learner heads (ridge / GB on V1 residual) reliably win

Agents 03, 04, 06, 08, 10 shipped ridge-linear or gradient-boosted residual
heads. Numbers:
- **agent-03**: GB head (R²=0.27–0.74 per platform) → **−30% yaw, −21% CTE**
- **agent-06**: 7-feature ridge (λ=30) → **−1.8% yaw, −5.3% CTE**
- **agent-04**: 8-feature nonlinear → **−5.5% yaw, −4% CTE**

All these beat rung-1 attempts on this cohort. The pattern: bias and
steering-rate interact nonlinearly with velocity; a low-rank linear
approximation to V1's empirical residual outperforms a 6-parameter
physics-inspired ODE that's poorly identified.

**Cite:** `agent-06/REPORT.md:22-26`, `agent-03/REPORT.md:14-22`,
`agent-04/REPORT.md:27-31`.

**M4 implication:** The router emits `try_residual_learner` with
`confidence: high` whenever the residual verdict is `noise_floor` on physics
levers but headroom remains on dev. Treat as the high-leverage rung-orthogonal
candidate.

---

## §5 — Lightning yaw saturates at +21% (platform-specific ceiling)

Cohort-median Lightning yaw improvement: **+22.2%, σ=2.1%** (tight). All
models — V0, V1, refined — cluster at ~0.0057 rad/s final. CTE improves to
+73% because trajectory integrates cleanly, but yaw RMSE has nowhere left to
go on Lightning specifically.

Mach-E shows σ=8.2%; IONIQ-5 shows σ=4.3% — much wider scatter, meaning
those platforms have unexploited headroom while Lightning does not.

**Cite:** `_grade/20260601-173918/cohort.md:120-126`.

**M4 implication:** When the gate flags a Lightning regression after a
Mach-E or IONIQ improvement, treat the Lightning regression as noise unless
it exceeds the cohort σ (2.1% absolute). Don't refit to recover it.

---

## §6 — Asymmetric (left vs right) steering response exists but overfits

Agent-07 discovered V1 residual left/right asymmetry: Mach-E turning-right
bias −0.0072 vs left −0.0003 (7× factor); IONIQ-5 similar. Built
`v1-asym-debias` with a gated bias `b_offset · 1[v > 2]`. **But**: joint
Nelder-Mead fit on 80-segment subsets flipped Lightning's signed bias and
degraded its CTE to 68 m, while the full-dataset fit was stable.

**Cite:** `agent-07/REPORT.md:21-44, 47-52`.

**M4 implication:** This is the direct empirical motivation for **k-fold
route-grouped CV** in the iterate gate. Naive subset fits overfit; route
grouping + variance bars catch it. Any candidate touching asymmetric levers
should specifically check the CV σ before being promoted.

---

## §7 — Fit-model skill absence blocked 2-3 agents from completing rung-1

Agents 03, 05, 06, 07 each spent 10-20 minutes hand-rolling parameter fitters
because the `fit-model/` skill listed in inventory was either absent or
incompatible with non-V1 model shapes. Agent-03: *"fit_dyn_st.py had
single-eval cost ~0.15 s/platform but under Nelder-Mead on IONIQ it did not
converge in budget."* Agent-06: *"lacked a parameter-identifiability
diagnostic — the rung-1 dynamic ST would probably win if C_αf, C_αr, Iz were
data-fit instead of carParams-fixed."*

**Cite:** `agent-03/REPORT.md:26`, `agent-06/REPORT.md:30`,
`agent-07/REPORT.md:59-67`.

**M4 implication:** `_shared/rung1_starter.py` exposes `fit_calpha_and_iz()`
exactly to close this tooling gap. The `iterate` skill's fit-diagnostic
propagation (co-collapse, stuck-on-bound, non-convergence) surfaces the
identifiability problem that agent-06 couldn't see.

---

## §8 — V1 lag-τ mis-models a non-linear structure (not transient)

Agent-03's lead-compensator optimiser actively *removed* the lag
(`K_d < 0`, `τ → 0.01`) across all platforms, yet a GB residual head on the
same residual achieved R²=0.68-0.74. Agent-05's v-dependent-lag grid search
collapsed back to V1's original τ.

Verdict (agent-03): *"V1's lag-τ isn't approximating transient slip — it's
mis-modelling a structure that's genuinely non-linear in the (δ, dδ/dt, v)
cube."*

**Cite:** `agent-03/REPORT.md:34-36`, `agent-01/REPORT.md:32`.

**M4 implication:** Lag-tuning is a dead-end. The transient residual lives
in a non-linear feature space; a true state-space rung-1 model targets it
correctly *if and only if* its parameters are properly fit (§1, §7), and a
residual learner approximates it from below (§4).

---

## Summary — the four moves m4 agents should know are evidence-backed

1. **Per-platform additive bias correction** (§2) → +3.7-4.6% CTE, zero structural cost.
2. **Residual learner head on V1** (§4) → +1-5% CTE, reliable across model shapes.
3. **Rung-1 dynamic ST WITH fit C_α + Iz** (§1, §7) → expected to work; never demonstrated because the cohort always used carParams. M4 starter exists specifically to close this gap.
4. **k-fold route-grouped CV on every candidate** (§6) → the discipline that prevents the agent-07 asymmetric-fit failure mode.

Avoid: linear steering-rate feedforward (§3), lag-τ refitting (§8),
single-subset fits on asymmetric levers (§6).

---

## §9 — m4.v1 cohort stragglers and the gates m4.v1.01 added in response

The m4.v1 cohort (10 agents, canonical eval 2026-06-02) ran median
**+56.2% yaw / +71.1% CTE**, basically tied with m3.v2 (**+56.6% / +72.2%**)
and m3.v3 (**+56.4% / +71.4%**). m4.v1's median agent was *not* the problem;
the mean was dragged by two stragglers:

| agent | yaw Δ% | CTE Δ% | failure mode |
|---|---|---|---|
| `m4.v1_agent-07` | +44.6% | +53.9% | per-platform bias fit on i.i.d. holdout; no route-grouped CV |
| `m4.v1_agent-10` | +39.3% | +36.6% | built on V0 (0.01293) instead of V1 (0.00587) |

Both agents made an early architectural decision and never iterated past
it. Token spend correlates: m4.v1 median was 2.43M (cheapest family in
the cohort) vs m3.v2's 4.49M and m3.v3's 5.50M. "Cheap" is the symptom;
the cause is that the template's guidance flagged the failure modes but
did not block them.

**The four gates m4.v1.01 introduced to close this:**

1. **`bias_without_route_cv` (hard refuse, in `skills/iterate/` and
   `skills/pre-flight-final-model/`).** If `coeffs.json` contains a
   per-platform bias-like field (`bias`, `bias_rad`, `delta_bias`, `d0`,
   `off`, etc.) without a `route_cv_sigma` sibling, the candidate is
   refused. Iterate refuses to log; preflight refuses to ship. Catches
   agent-07's exact mode.
2. **`parent_baseline_declared` (lock-time + preflight).** PLAN.md must
   have a `## Parent baseline` section naming V0 / V1 / fresh with a one-
   line evidence citation. `rpi/lock.sh` refuses to lock PLAN.md
   otherwise. Catches agent-10's V0 anchoring before any fit runs.
3. **`iterate_history_min` ≥ 4** EXPERIMENTS.md entries written by
   `skills/iterate/`. Replaces the gameable `models_md_has_min_candidates
   ≥ 4` file-count check; agent-07 had no MODELS.md iterations at all.
4. **`report_cites_rejected`** — REPORT.md must have a
   `## Candidates considered and rejected` section with ≥ 1 verdict
   marked shelved / rejected / did not ship. Forces the explicit
   comparison agent-07 skipped.

**The inline routing change:** `critique-residuals` now emits
`add_route_cv_for_bias` as the highest-priority route when the iterate
gate has already flagged `bias_without_route_cv`. The cohort §6 prior is
now wired into the router the agent sees after every iterate call, not
just the references on disk.

**The structural change:** the `launch-rungs/` fan-out grew from 4 to 6
subagents — added `rung-0-orth-gb` (cohort §4 next step) and
`rung-2-lightning-targeted`. Lightning is the headroom platform: m4.v1
ran +21% yaw on Lightning vs +55% on Mach-E/IONIQ. The new subagent
exists to close that gap.

**The budget change:** orchestrator 45 → 90 min; subagents 25–30 → 45–60
min. The cohort signal is that time pressure (real or imagined) caused
agents to skip route-CV and ship single candidates. Removing the
pressure removes the rationalisation.

**Cite:** `m4.v1_agent-07/REPORT.md`, `m4.v1_agent-10/REPORT.md`,
`_grade/20260602-215951/cohort.md`.
