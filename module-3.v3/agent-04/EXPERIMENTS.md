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

- (structure) **Residual learner on V1** — feed-forward correction `b0 + b1*|delta|*delta + b2*v*delta + b3*v^2*delta` fit on V1 residuals; attacks tyre-saturation residual visible as |delta|*delta correlation +0.25/+0.35 on Lightning/Mach-E.
- (structure) **Rich residual learner with transient terms** — adds delta^3, ddelta/dt, ddelta/dt*v, sign(delta)*delta^2*v; attacks both tyre saturation and the V1 transient-regime residual (RMSE 0.0165 in transient vs 0.0044 straight).
- (structure) **Dynamic single-track ODE (rung-1 bicycle)** — replace kinematic with proper m*v*(beta_dot + r) = Fy_f + Fy_r dynamics; integrate state (beta, r). Considered but not pursued in time: cornering-stiffness identifiability concerns and per-platform priors needed.
- (structure) **Regime-switched composite** — V1 for straight + dynamic model for high-|a_lat_proxy| regime. Considered; deferred because the residual learner already captures the saturation signal cheaply.
- (refines-v1) **Refit V1 coefficients with CTE-weighted loss** — keep V1 shape, weight loss by CTE contribution. The m3.v2 cohort already converged here; expected payoff <1% per AGENTS.md.
- (orthogonal) **Per-route bias correction at inference time** — estimate per-segment yaw mean from low-curvature samples and subtract. Equivalent to extending V1's per-segment δ₀ logic to non-straight portions. Considered; competes directly with the bias term in the residual learner so kept the simpler unified approach.

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

## E01 — Residual-feature correlation scan

- Hypothesis: V1's residual has structure correlated with simple input features.
- What I did: per-platform Pearson correlation of (yaw_truth - yaw_v1) against
  {v, delta, ddelta/dt, v*delta, v^2*delta, yr_v1, a_long, |delta|*delta}.
- Result: `|delta|*delta` was the dominant signal — corr +0.25 on Lightning,
  +0.35 on Mach-E, weak (+0.03) on IONIQ-5. This is the **tyre-saturation**
  signature: V1's linear understeer cannot bend the response curve at high δ.
- Verdict: keep — drives the choice of correction features.
- Rules out: a single global bias as the dominant residual (means are ≤0.002).

## E02 — v1_plus_nonlin (residual learner, 4 features)

- Model dir: models/v1_plus_nonlin/
- Hypothesis: ridge-fit a {1, |δ|δ, vδ, v²δ} correction on V1 residuals will
  close the tyre-saturation gap without altering V1's transient dynamics.
- What I changed vs E01: built `predict.py` that adds X·β to predict_v1 output.
- Result (dev pooled): yaw 0.005874 → 0.005600 (-4.7%); CTE 56.81 → 54.37 (-4.3%).
  Mach-E CTE drift: -22.0 m → -5.8 m.
- Verdict: keep.
- Rules out: V1's understeer constant being well-fitted at high δ — the |δ|δ
  coefficient is large (+0.49 on Mach-E) and statistically significant.

## E03 — v1_plus_rich (8-feature correction with transient terms)

- Model dir: models/v1_plus_rich/
- Hypothesis: adding `ddelta/dt`, `delta^3`, and `sign(δ)·δ²·v` will also
  attack V1's transient-regime residual (transient yaw RMSE 0.0165 vs steady
  0.0083).
- What I changed vs E02: added 4 features; refit on same data.
- Result (dev pooled): yaw 0.005552 (-5.5% vs V1); CTE 54.56 (-4.0% vs V1).
  Per-regime: transient 0.01647 → 0.01565 (-5.0%); steady 0.00835 → 0.00754 (-9.7%).
- Verdict: ship.
- Rules out: needing a full dynamic-single-track ODE — `ddelta/dt` as a static
  feature captures most of the transient signal V1's tau-lag misses.
