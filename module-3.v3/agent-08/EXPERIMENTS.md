# EXPERIMENTS.md

## Alternatives considered

Per `references/exploration-discipline.md`, at least five alternative model
structures must be named, three structurally distinct from V1.

- (refines-v1) **v1-refit** — same kinematic-single-track + understeer + lag shape;
  refit coefficients only. Sanity-check.
- (structure) **v1-plus-residual** — linear per-platform additive residual on
  allowlist-derived features (ddelta, v·delta, v·ddelta, |v0_yaw|, ...) trained
  on `truth - V1`. Attacks transient + per-platform bias residual.
- (structure) **dynamic-single-track (rung-1)** — linear bicycle with cornering-stiffness
  dynamics. States (v_y, ψ̇), fits per-platform (a, C_f, C_r). Attacks Mach-E
  transient-regime residual structurally.
- (structure) **regime-switched composite** — V1 for `|delta_road| < 0.01`, dynamic-
  single-track in cornering regime. Keeps V1's straight-row noise-floor
  performance.
- (structure) **complementary filter on yaw** — blend V1's low-frequency yaw
  with a high-frequency signal from `d(delta)/dt` and a per-platform gain.
  Two scalar mixers per platform.

Three of the above ((structure)-tagged) are structurally distinct from V1.

---

## E00 — V1 baseline (reproduced)

- Hypothesis: V1 is the pre-shipped rung-0 ceiling. Confirm the floor.
- Result (local pooled): yaw 0.00762 rad/s; CTE 75.65 m.
- Per-platform matches AGENTS.md table cell-for-cell (Lightning 0.00566/62.2,
  Mach-E 0.00859/98.7, IONIQ 0.00766/69.5).
- Verdict: baseline.

## E01 — Residual structure scan

- Model dir: n/a (diagnostic).
- Hypothesis: `truth - V1` has a per-platform mean offset and `ddelta`-correlated
  shape that a per-sample linear correction can absorb.
- Result: Mach-E mean residual +3.6e-3 (under-predicts), Lightning -3.1e-3,
  IONIQ +1.9e-3. Slope `resid ~ beta * ddelta` flips sign across platforms.
- Verdict: per-platform linear correction is the right scope. Justifies
  v1-plus-residual.

## E02 — v1-plus-residual (10 features, ridge)

- Model dir: models/v1-plus-residual/.
- Hypothesis: A small allowlist-feature linear regression on the V1 residual
  closes the transient and per-platform-bias components.
- What I changed vs V1: added `+ X @ beta_platform` to V1's output where X is
  10 features.
- Result (dev pooled): yaw 0.00762 → 0.00738 (-3.1%); CTE 75.65 → 71.77 (-5.1%).
  - Per platform: Lightning -5.2% yaw / +3.3% CTE; Mach-E -5.3% yaw / -5.2%
    CTE; IONIQ -2.0% yaw / -6.7% CTE.
- Verdict: **ship**.
- Things this rules out: the residual is not a *pure* steady-state offset
  (the `ddelta` features carry weight) but it is captured by linear shape.

## E03 — richer features (tried but shelved)

- Hypothesis: cubic-delta, v0·|v0|, dv0/dt, low-pass-filtered ddelta close
  more residual.
- Result: ~0.5% additional yaw RMSE drop. Identifiability/co-collapse risk
  rises.
- Verdict: shelve. Diminishing returns within time budget.

## E04 — dynamic-single-track (drafted only)

- Model dir: models/dynamic-single-track/.
- Hypothesis: linear bicycle replaces V1's single-pole-lag approximation with
  the actual cornering-stiffness dynamics; would attack Mach-E transient regime
  more directly than the residual learner.
- Result: not implemented. Formulation in `notes.md`. predict.py falls through
  to V1.
- Verdict: drafting. Hand-off candidate for next cohort agent.
