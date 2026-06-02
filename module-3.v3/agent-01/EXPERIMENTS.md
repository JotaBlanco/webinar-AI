# EXPERIMENTS.md

Append-only log of attempts. One entry per concrete attempt.
See `references/exploration-discipline.md` for why.

## Alternatives considered

**Preflight requires ≥5 bullets here, with ≥3 tagged `(structure)`.**

Fill this in **before** building your first candidate, based on V1's residual
diagnosis (see `AGENTS.md` § "V1's residual diagnosis"). Each bullet: one line
naming a *model shape* (not a coefficient tweak) and the V1 residual it
attacks. Tag with `(structure)` if it differs from V1's kinematic-single-track
form, `(refines-v1)` if it stays inside V1's shape, `(orthogonal)` if it's a
non-modelling intervention (ensembling, multi-seed averaging).

- (structure) **bias-corrected-v1** — V1 + per-platform additive yaw-rate bias term learned offline. Attacks the residual CTE drift (Mach-E −22m, IONIQ −12m) that survives V1; structurally adds an extra fitted state (constant offset on yaw_rate output) outside V1's single-track equations.
- (structure) **steering-derivative residual learner** — V1 + a linear residual model `r̂ = a·(dδ/dt) + b·v·dδ/dt + c·sign(δ̇)` fit on the V1 residual. Attacks transient yaw error on Mach-E (regime rmse 0.0165) which the first-order lag under-models.
- (structure) **v-dependent lag (rung-1-lite)** — replace V1's scalar τ with τ(v) = τ0 + τ1/v so the lag responds harder at low speed (where transients dominate CTE). Differs from V1 because τ is no longer a single fitted scalar.
- (structure) **regime-switched composite** — V1 for straight + steady, a separately-tuned V1 (or steering-derivative-driven correction) for transient. Differs because the predict has a state-machine selector V1 can't reach by refit.
- (refines-v1) **refit-v1-cte-objective** — refit V1's (g, L_eff, K_us, τ, δ0_fallback) jointly minimising CTE, not yaw RMSE. Sanity refit; tests whether the cte-drift can be killed without new structure.
- (orthogonal) **ensemble** — average yaw_rate of V1 and the bias-corrected variant. Non-modelling intervention used only if both win on different platforms.

---

## Log entry schema

```
## E<NN> — <one-line approach name>
- Model dir: models/<name>/   (if applicable)
- Hypothesis: why you thought this would help, in one line.
- What I changed vs E<NN-1>: the minimal diff.
- Result (dev pooled): yaw <old> → <new> (Δ% vs V1); CTE <old> → <new> (Δ% vs V1).
- Verdict: keep | shelve | revisit-later.
- Things this rules out: what you learned, even if the experiment failed.
```

Tag every entry with the model dir (when applicable) so the link to MODELS.md is
explicit. **The shipped model must differ structurally from V1** — preflight
warns if your shipped predict is functionally identical to V1.

---

## E00 — V1 baseline

- Hypothesis: V1 is the pre-shipped rung-0 ceiling. Score it to confirm the
  floor and to read the per-platform residual breakdown.
- What I did: ran `score-model` on `code.v1_baseline.predict_v1`.
- Result (dev pooled): yaw 0.005874 rad/s; CTE 56.81 m.
  - Per-platform: Lightning yaw 0.00566 / CTE 62.2; Mach-E yaw 0.00859 / CTE 98.7;
    IONIQ-5 yaw 0.00766 / CTE 69.5; Tesla 0/0 (passthrough).
- Verdict: baseline. **Next: diagnose what's left.**

## E01 — bias-corrected-v1 (SHIPPED)
- Model dir: models/bias-corrected-v1/
- Hypothesis: V1's residual CTE drift is bias-dominated; a small per-platform yaw offset on V1's output should integrate away the drift.
- What I changed vs V1: add scalar offset to V1.predict output (per-platform). Mach-E +0.00210, IONIQ +0.00108, Lightning 0.
- Result (dev pooled): yaw 0.005874 -> 0.005843 (-0.5%); CTE 56.81 -> 54.19 (-4.6%).
- Verdict: KEEP. Ship.
- Things this rules out: nothing — confirms diagnosis (bias is the dominant residual on Mach-E/IONIQ).

## E02 — steering-derivative-residual
- Model dir: models/steering-derivative-residual/
- Hypothesis: V1's transient yaw error correlates with steering rate; a small linear residual learner on (dδ/dt, v·dδ/dt, sign·sqrt|δ̇|, 1) should improve both yaw and CTE.
- What I changed vs E01: replaced scalar offset with a 4-feature ridge-fit linear residual per platform.
- Result (dev pooled): yaw 0.005827 (-0.8%); CTE 54.51 (-4.0%).
- Verdict: SHELVE. Yaw fractionally better, CTE fractionally worse. Complexity not earned.
- Things this rules out: the constant term dominates the residual learner; the dδ/dt features barely contribute. Most of the CTE win is just bias correction in fancier dress.

## E03 — v-dependent-lag
- Model dir: models/v-dependent-lag/
- Hypothesis: V1's scalar lag τ should grow at low v (where transients dominate CTE).
- What I changed vs V1: τ(v) = τ0 + τ1 / max(v, 1), grid-search per platform.
- Result (dev pooled): yaw 0.005871 (-0.05%); CTE 56.74 (-0.1%). Both inside noise.
- Verdict: SHELVE.
- Things this rules out: scalar lag is already well-fit; the transient regime residual is not lag-misfit. Next agent should not climb rung-1 dynamics motivated by lag.
