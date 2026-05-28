---
title: Best practices and anti-patterns for lateral-fidelity modules
summary: Distilled advice for agents working on idea-01 (lateral yaw-rate fidelity). Captures what prior cohorts did right, what they did wrong, and where the traps are. Designed to be loaded into a module's M3-style README — concise, opinionated, and explicit about uncertainty.
updated: 2026-05-28
---

# Best practices and anti-patterns — lateral-fidelity modules

This file is the orchestrator's curated knowledge for agents that work on idea-01 (improve the lateral yaw-rate prediction of the KS model). It is the result of running ~85 agents across one raw cohort and 15 scaffolded cohorts on this exact task and reading every report.

**Use it as inspiration, not law.** Every claim here can be wrong on your specific problem. If you find evidence to the contrary, follow the evidence. The only obligation is to lower the canonical RMSE on the held-out val-data.

---

## How you will be scored

Your final model is run against a **held-out validation pool** under [F1/KB003/data/val-data/](../../../../F1/KB003/data/val-data) — segments you have never seen. The scoring spec lives in [idea-01-lateral-attribution.canonical.yaml](../domain-knowledge-challenges/idea-01-lateral-attribution.canonical.yaml).

The val pool is held out by **whole route** (~24% of routes per platform, seed 42). Segments from the same route stay together, so memorising a route is not a winning strategy. Platforms in scope: `FORD_MUSTANG_MACH_E_MK1` and `FORD_F_150_LIGHTNING_MK1`. Tesla has no usable yaw-rate truth — exclude it. Sample filter: `v_mps > 2.0` (in-motion only).

What this means in practice: any "model" you ship must be a function that takes a new segment's columns and returns predictions. A list of per-segment biases you fit on the train pool will not transfer to the val pool — the val segments are different.

### Primary KPIs

There are **two primary KPIs**. Neither dominates the other; a model that wins on one but loses on the other tells you something specific (see the diagnostic table below). The model you want wins on both.

#### KPI 1 — Yaw-rate RMSE

- **Definition:** `sqrt(mean((ψ̇_pred − ψ̇_meas)²))` pooled over all in-motion samples (`v_mps > 2.0`) across the val pool.
- **Unit:** rad/s.
- **Truth channel:** `yaw_rate_meas_rads` (the measured CAN bus yaw rate).
- **Baseline V0:** the unmodified KS model's `yaw_rate_pred_rads` column, already present in each `sim.csv`.
- **Improvement formula:** `(V0_RMSE − your_RMSE) / V0_RMSE × 100`. Positive = better.
- **What it captures:** instantaneous lateral fidelity. Penalises noise and bias in the yaw rate prediction at every sample.
- **What it misses:** persistent low-amplitude biases that look small per-sample but integrate to large heading and position errors over time.

#### KPI 2 — Distance-resampled cross-track-error RMSE

- **Definition:** for each segment, integrate both the predicted and truth trajectories from (x=0, y=0, ψ=0), then sample the cross-track error (signed perpendicular distance from the predicted point to the truth trajectory) onto a uniform **1m distance grid** along the truth trajectory. Pool all `(segment, distance-bin)` pairs across the val set and take RMSE.
- **Unit:** meters.
- **Truth trajectory:** `x = ∫ v_meas · cos(ψ) dt`, `y = ∫ v_meas · sin(ψ) dt`, `ψ = ∫ ψ̇_meas dt`, anchored at (0, 0, 0). This is what `viz_compare_rerun.py::compute_real_trajectory` already computes — reuse the logic, don't re-derive it.
- **Predicted trajectory:** the same integration but using the agent's predicted yaw rate (and the measured `v_mps`, since velocity is clamped under the operating contract).
- **Baseline V0:** the same calculation using V0's `yaw_rate_pred_rads`.
- **Minimum segment travel:** segments whose truth trajectory accumulates less than **20m** of travel are excluded (too short to develop measurable drift; would dilute the metric with noise).
- **Improvement formula:** `(V0_CTE_RMSE − your_CTE_RMSE) / V0_CTE_RMSE × 100`. Positive = better.
- **What it captures:** cumulative trajectory drift. A persistent yaw-rate bias of even 0.001 rad/s, undetectable in KPI 1 noise, will accumulate to a measurable CTE here.
- **What it misses:** high-frequency yaw-rate noise that doesn't accumulate (averages out over the trajectory). A noisy but unbiased model can score well here while being unsafe to use in control.

### Reading both KPIs together

| Pattern | Likely cause |
|---|---|
| Wins yaw rate, loses CTE | Yaw rate is noisy but unbiased; a small systematic bias survives the RMSE pool and accumulates in trajectory. |
| Loses yaw rate, wins CTE | Yaw rate has big oscillations that average out over distance; or the model predicts conservatively (small variance) and lucks out on the integration. |
| Wins both | Real improvement. Ship it. |
| Loses both | Real regression. Don't ship. |

### Diagnostic metrics (reported but not primary)

These help you debug; they're not what you're optimising:

- **CTE at distance checkpoints** (30m, 100m, 300m). Mean cross-track error at the moment the truth trajectory has covered that distance. Useful for seeing *when* the model drifts.
- **Heading drift rate** β_ψ. For each segment, fit Δψ(s) = α + β·s as a linear model where s is distance along the truth path. Mean |β| across segments, units rad/m. Strips out the noise and shows whether your yaw rate has a *systematic* component that accumulates. A model with β_ψ near zero has unbiased yaw rate; a high β_ψ has bias even if KPI 1 looks fine.
- **Per-platform breakdowns** of both primary KPIs. The Mach-E and F-150 Lightning have different dynamics; if your model wins on one and regresses on the other, the headline averages can hide that.

---

## Lessons distilled — read these first

Prior cohort: ~85 agents on this exact task across one raw baseline and 15 scaffolded variants. The five principles below cost prior agents 15–60 canonical points each time they were ignored. They are the meta-framing for the specific anti-patterns later in this file.

1. **Aim at the canonical KPIs. Nothing else.** Scaffolding is a force vector, not a force multiplier — whatever it points at, agents go toward. Prior agents who optimised against rubric items or in-sample slices delivered defensible reports with worse canonical numbers. Every iteration must close its loop against the canonical KPIs above (yaw-rate RMSE + CTE RMSE on the held-out val pool), not against "skill passes" or "report looks complete."

2. **Tools we hand you are starting points, not recipes.** Every prior angle that shipped a runnable Python recipe (`triage.py`, `step4_run_st_upgrade.py`, etc.) plateaued at that recipe's reach — capped Cα bounds capped the ceiling; hardcoded `--platform FORD_MUSTANG_MACH_E_MK1` defaults capped the dataset; named `V1, V2, V3, V4` rungs capped the variant space. The only family that beat raw was the one that documented constraints without prescribing methodology. Modify, extend, or delete any tool we give you. Document what you changed and why.

3. **Self-evolution amplifies whatever target you point it at.** The prior cohort module that evolved its scaffolding against the canonical baseline gained 31 points (Angle C M3). The one that evolved against rubric lost 15 points (Angle A M4). Same mechanism, opposite outcome. If you iterate, your stop condition must be canonical KPI improvement — not "skill is patched" or "rubric items pass."

4. **Force diversity. Don't ship the first thing that beats V0.** Variance collapses faster than mean rises — prior cohorts had 5-agent families converge on identical numbers with zero standard deviation, all running the same V1 per-segment-bias trick. Explore at least three distinct variants before declaring a favourite, with at least one outside any prescribed ladder. If your variants all look like each other, you haven't searched.

5. **Lock the evaluation pool before fitting.** Pick the segments, truth channel, and filter before you fit anything. Prior agents who fit on Mach-E only and shipped a model that got applied to both Ford platforms canonically scored at −60% or worse. From your first variant onwards, evaluate on the same pool the grading skill will use: both Ford platforms, the `v_mps > 2.0` filter, both KPIs.

The single-sentence version: **"Start from what we give you. Propose extensions. Justify them against the canonical metric. Diversify."**

---

## If you split your own train into train/dev for iteration

You have the train pool under [webinar-AI/data/](../../data/). If you want to evaluate yourself before shipping, split a dev set out of it. The split rules below are what prior cohorts got wrong; copy them, don't reinvent them.

1. **Hold out whole segments, never interleaved samples.** Within a 50 Hz segment, adjacent samples are tightly correlated (the car barely moves between samples). Splitting "every 5th sample to test" leaks ~99% of the information across the boundary; your dev RMSE will look great and won't predict your val RMSE at all. *This is the Angle C M2 mistake from the prior cohort: dev numbers said "+6%", canonical val said "−13%".*

2. **Hold out by route + device combination, not by random segment.** Segments from the same drive are too similar to their neighbours — same road, same driver, same vehicle dynamics state. Test on different drives. The val split does this; your dev split should too. The existing val-split.json under `val-data/split.json` is a worked example.

3. **Stratify by platform.** Mach-E and F-150 Lightning have different wheelbases, masses, and steering ratios. If your dev set is 90% Mach-E, a model that's only good on Mach-E will look great on dev and regress on val. Keep platform proportions matched train/dev.

4. **Keep at least 20–30% in dev.** Smaller and the noise dominates: a single bad segment can swing your dev RMSE by 5%+. Larger and you've thrown away training data.

5. **Don't peek at the val pool.** Even just `ls`-ing it. The instinct to "let me just sanity-check the val data exists" frequently becomes "let me check what's in it" which becomes "let me tune against it." Trust that it exists.

---

## Anti-patterns from prior cohorts (don't repeat these)

### Fitting on Mach-E only and shipping for both platforms

Several prior agents fitted parameters (`Cα`, `K_us`, effective wheelbase) on just `FORD_MUSTANG_MACH_E_MK1` and shipped a model that gets applied to both Ford platforms. Canonical eval pooled platforms; their Mach-E gain didn't transfer to F-150 and they regressed catastrophically (one agent: canonical −94%). **Fix:** if you fit per-platform parameters, fit them per-platform. If you fit pooled parameters, evaluate on both platforms before shipping.

### Pinning to V1 (per-segment yaw-gyro bias)

The "V1 trick" — KS recalibrated + per-segment straight-line yaw-gyro bias subtracted — gave exactly **+10.9%** on the prior cohort's in-sample yaw-rate eval. It is mathematically guaranteed to improve in-sample yaw-rate RMSE by removing the per-segment mean error. The prior cohort had 5 of 5 Angle-E agents converge on exactly this number with zero variance. **Three issues now:** (a) on the held-out val pool, the per-segment bias can't be pre-fit — your model must compute it from the val segment itself at score time, and the bias is then noisier; (b) the per-segment mean assumes the bias is constant over the segment, which it isn't, so a residual time-varying bias survives and shows up as cross-track drift in KPI 2; (c) +10.9% is a floor on KPI 1, not a ceiling. Many raw agents reached +30–49% on yaw rate by adding understeer terms on top — and crucially, those models also score better on KPI 2 because the understeer term reduces the actual physical bias rather than averaging it away.

### Treating "interpretability over accuracy" as a hard rule

The prior cohort's Angle B substrate told agents *"interpretability usually wins unless the accuracy gain is decisive."* Result: agents preferred physically clean Linear-ST fits even when per-segment numerical tricks would have won. **Both can be right.** Use whichever lowers canonical RMSE. If a residual learner on top of a physical model is what wins, ship it.

### Optimising for rubric pass instead of canonical RMSE

The prior cohort had a rubric eval that checked items like "did you name the truth channel? did you acknowledge the operating contract?" Self-evolution loops pointed at this rubric drove agents to produce defensible reports with mediocre numbers. **Be explicit with yourself about the metric you're optimising.** Rubric items are hygiene, not outcome.

### Trusting bounds in scaffold-supplied tools

Prior cohorts' `triage.py` shipped `C_α` bounds of `(5e4, 5e5)` N/rad. If an L-BFGS fit pegs at the upper bound, that's not "Cα is 5e5", that's "the bound is wrong for this platform." **If a fit pegs a boundary, widen the boundary and re-fit.** Don't take ship-supplied numbers as physical constants — they're inherited priors and can be wrong.

---

## Things that have worked

Not recipes — directions that have produced sustained gains in prior cohorts. Pick whichever your evidence supports.

- **Per-platform parameter fits.** Both Ford platforms have different `(L, m, l_f, l_r, C_α)`. Fitting these per-platform (rather than pooling) consistently helps. The raw agents who scored +40%+ all did this.
- **Understeer correction (`K_us · v²` term).** The KS model has zero understeer; real cars have non-zero. Adding the understeer term from the Linear single-track model (with per-platform K_us fit on the train set) is one of the highest-leverage single changes. Several raw agents reached +30%+ from this alone.
- **Per-segment yaw-gyro bias removal on straight rows.** The +10.9% V1 trick. Use as a floor, not a ceiling. If you add it, add an understeer term on top.
- **Steering-lag compensation (a few samples shift).** Sometimes worth ~2–4%. Easy to overfit — bound the lag tightly and validate on dev.
- **Residual learning on top of a physical prior.** Fit the physical model first (KS + understeer + bias), then learn what's left with a small linear or ridge model over `[v, |a_y|, |δ|, sign(δ̇)]`. The best Angle A agent did this and reached +54.9%.
- **Interleaved-train-test for hyperparameter tuning *within* your own train pool.** Different from splitting your dev set (don't do that — see anti-patterns). For tuning regularisation, interleaved is fine.

---

## On the scaffolding we hand you

Whatever skills, scripts, or READMEs we provide are starting points. We don't always know what's best for your task. Concretely:

- **You may modify any tool.** If `triage.py` is wrong about something, fix it. Document the fix.
- **You may delete any skill.** If a skill is making your work harder, throw it away. Don't pretend to use it.
- **You may invent new variants.** No "V1, V2, V3, V4" ladder is sacred. If you find a V5 that beats them all, ship V5.
- **You may go off-physics.** If a pure-statistical model wins, ship it. Annotate that you're choosing accuracy over interpretability.
- **The only thing you cannot do** is fabricate val-data results, evaluate on data you didn't train on by accident (touch the val pool), or claim a number you can't reproduce.

If the substrate we hand you contradicts this file, this file wins.

---

## On reporting

When you submit:

- State your variant clearly. One name, one definition. If you shipped V4, say so and quote the line in your script where V4 is computed.
- Save the coefficients. JSON under `out/coeffs.json` is the lowest-friction format. The grading judge will load it.
- Save (or import) the predict function. If your model is "load coeffs and apply equation E", state E in the report. If your model is "call function f in tools/foo.py", make sure f is callable from outside your folder without side effects.
- Report both the in-sample and the held-out number if you computed both. The gap between them is a generalisation diagnostic worth knowing.
- Be honest about regressions. If V4 looked good on dev but V2 was actually your best, ship V2 and say so.
