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

- (structure) **v1-plus-resid** — additive linear residual learner on top of V1's yaw output, fed allowlist features (v, δ, dδ/dt, a_long, yr_v1, |δ|, sign(yr_v1)·yr_v1²). Attacks the *non-bias* residual that V1's pure-physics shape can't capture (regime-dependent miscalibration). structure: differs-from-v1.
- (structure) **steer-rate-ff** — V1 + a derivative feedforward k_ff·v·dδ/dt. This turns V1's first-order pole into a lead-lag transfer function — a *new pole-zero structure*, not a refit. Attacks transient-regime yaw error on Mach-E. structure: differs-from-v1.
- (structure) **v1-cte-debiased** — V1 + per-platform constant yaw offset chosen to *minimise pooled CTE* (not yaw RMSE). Objective-function change: cost is the integrated trajectory error, not sample-wise yaw RMSE. structure: differs-from-v1.
- (refines-v1) **v1-refit** — refit V1 coefficients on the full sim/ data with a stricter δ₀ filter. Sanity check; expected ≈V1.
- (orthogonal) **blended-ensemble** — average yaw of v1-plus-resid and v1-cte-debiased (geometric mean of trajectories). Could absorb their respective improvements; orthogonal to the modelling layer.

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
- Per-regime yaw: straight 0.00442; steady 0.00835; transient 0.01647.
  Mach-E and IONIQ-5 have signed CTE drift of −22 m and −12 m respectively —
  CTE residual is bias-dominated, not noise-dominated.
- Verdict: baseline. **Diagnosis: Mach-E/IONIQ-5 cte_drift is the target;
  transient yaw is secondary.**

## E01 — v1-plus-resid (additive linear residual learner)

- Model dir: `models/v1-plus-resid/`
- Hypothesis: V1's residual contains structure that is linearly predictable
  from {v, δ, dδ/dt, a_long, yr_v1, |δ|, sign(yr_v1)·yr_v1²} — that's exactly
  the structure that any single-pole physical model misses.
- What I changed vs V1: added a per-platform 7-feature ridge regression that
  emits an additive yaw correction on top of V1.
- Result (dev pooled): yaw 0.005874 → 0.005727 (−2.5% vs V1);
  CTE 56.81 → 54.30 (−4.4% vs V1).
- Per-platform yaw: Lightning 0.00566→0.00550; Mach-E 0.00859→0.00815;
  IONIQ-5 0.00766→0.00755. All signed yaw biases collapse to ≈0.
- Verdict: **keep — shipped**. R² of the residual fit is only 0.02–0.07, but
  even at that R² it picks up the CTE-relevant bias structure.
- Rules out: "V1's residual is pure white noise" — it is not; there is
  signal there, just spread across many small effects.

## E02 — steer-rate-ff (V1 + derivative feedforward)

- Model dir: `models/steer-rate-ff/`
- Hypothesis: V1's first-order lag is a band-aid for a missing zero in the
  steering-to-yaw transfer. Adding k_ff·v·dδ/dt should attack the transient
  regime, which carries V1's worst yaw error.
- Result (dev pooled): yaw 0.005874 → 0.005832 (−0.7%); CTE 56.81 → 54.46 (−4.1%).
- Verdict: shelve in favour of E01. Improvement is real but smaller; the
  bias term it learns ends up doing most of the work, not the derivative.
- Rules out: "the transient regime carries enough signal for a single
  feedforward gain to be the main win" — at the data's noise level it doesn't.

## E03 — v1-cte-debiased (CTE-objective offset)

- Model dir: `models/v1-cte-debiased/`
- Hypothesis: pooled CTE is dominated by signed yaw bias × distance. Choose
  one constant per platform that minimises pooled CTE directly, not yaw RMSE.
- Result (dev pooled): yaw 0.005874 → 0.005843 (−0.5%); CTE 56.81 → 54.19 (−4.6%).
- Verdict: shelve in favour of E01 — beats E01 marginally on CTE but loses on
  yaw RMSE by 2 pp. E01 wins jointly. Confirms that ≥80% of the CTE gap from
  V1 is closeable with a single bias coefficient — the bigger CTE-RMSE pool is
  segment-level noise, not platform-level bias.
- Rules out: "the remaining Mach-E CTE is the same as the yaw RMSE story".
  It's not — fixing the bias still leaves 91 m of Mach-E CTE, which is
  segment-shape noise, not platform-mean drift.
