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

- (structure) **Rung-1 dynamic single-track ODE** — lateral dynamics with cornering stiffness on front/rear axles; attacks Mach-E's transient-regime yaw residual (RMSE 0.0086, ~2× Lightning) by replacing V1's first-order lag (band-aid) with the real second-order tyre/slip dynamics.
- (structure) **Feed-forward derivative correction** — V1 + k_ff · d(δ_road)/dt, gated by |δ_road|, attacking transient yaw overshoot left by the 1st-order lag. Differs from V1 because V1 has no derivative-of-input term.
- (structure) **Regime-switched composite** — V1 for straight + a transient-only correction layer driven by ḋ and ä; explicitly switches model shape by regime mask. Differs from V1 (V1 is a single shape across regimes).
- (refines-v1) **Per-platform affine post-correction** — y = s·y_v1 + b fit on truth, attacking the residual signed yaw bias on Mach-E (-0.00142) and IONIQ-5 (-0.00075) that drives the bulk of pooled CTE. Same shape as V1; refines it.
- (orthogonal) **Mean of V1 and feed-forward correction with platform-weighted blend** — non-modelling intervention; treat as fallback if individual candidates underperform.

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

## E01 — v1_plus_delta0 (per-segment δ₀ everywhere)
- Model dir: models/v1_plus_delta0/
- Hypothesis: V1 only enables per-segment δ₀ for Mach-E and IONIQ-5; let it float for Lightning too.
- Result (dev pooled): yaw 0.005874 → 0.006012 (+2.3%); CTE 56.81 → 69.70 (+22.7%).
- Verdict: shelve. Lightning's V1 calibration is stable with a fixed δ₀; per-seg median introduces +0.005 rad of yaw bias on Lightning.
- Ruled out: per-segment δ₀ as a universal default.

## E02 — v1_plus_ddelta (feed-forward d(δ)/dt)
- Model dir: models/v1_plus_ddelta/
- Hypothesis: V1's first-order lag leaves residual structure correlated with d(δ_road)/dt during transients.
- Result (dev pooled): yaw 0.005874 → 0.005872 (-0.03%); CTE 56.81 → 56.81 (~0%).
- Verdict: shelve. Negligible gain on pooled metrics. Fitted k_ff values are real (-0.013 Lightning, -0.010 Mach-E) but the corrections are tiny relative to V1 residual variance.
- Ruled out: standalone derivative term as a path to win.

## E03 — v1_affine (per-platform s, b correction)
- Model dir: models/v1_affine/
- Hypothesis: signed yaw bias on Mach-E and IONIQ-5 (which drives CTE drift) is removable by a 2-scalar affine map y = s·y_v1 + b per platform.
- Result (dev pooled): yaw 0.005874 → 0.005815 (-1.0%); CTE 56.81 → 54.48 (-4.1%).
- Holdout (route-grouped 70/30): pooled yaw 0.006991 → 0.006954; CTE 52.72 → 52.29. Mach-E and IONIQ-5 gained; Lightning LOST on CTE (49.7 → 56.5).
- Verdict: ship — but Lightning forced to pass-through to V1 based on holdout signal. Final Mach-E s=0.986 b=+0.00144; IONIQ-5 s=0.994 b=+0.00073; Lightning s=1.0 b=0.0.
- Ruled out: blindly applying the same correction shape across platforms; per-platform holdout is required.

## E04 — v1_combined (s, b, k_ff per platform)
- Model dir: models/v1_combined/
- Hypothesis: combining the affine bias correction (E03) with the d(δ)/dt feed-forward (E02) gives both wins together.
- Result (dev pooled): yaw 0.005815 → 0.005813; CTE 54.48 → 54.47.
- Verdict: shelve. k_ff is redundant once affine bias is fit jointly — the post-affine residual no longer correlates with d(δ)/dt at a level worth the extra parameter. Ship the simpler 2-param `v1_affine`.
- Ruled out: stacking small structural additions on top of an affine bias fix.
