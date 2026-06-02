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

- (structure) **Nonlinear understeer (cubic K_us)** — V1 uses linear understeer `L_eff + K_us*v^2`; add a cubic-in-lateral-accel term to model tyre saturation. Attacks Mach-E's high-|a_lat| residual that grows from -0.003 to -0.012 between |a_lat_proxy| 0.5 and 5.
- (structure) **Affine post-correction on V1 yaw** — `yr = a * yr_v1 + b` per platform, with `a, b` fit on V1 residual. Structurally different because it abandons single-track-physics-only and treats V1 as a feature. Attacks both yaw-scale residual (Lightning bias) and CTE drift.
- (structure) **Steering-rate transient feature** — V1's first-order lag is a single-pole. Augment yr_v1 with a `d(delta_road)/dt` term: `yr = yr_v1 + c * ddelta_dt`. Attacks Mach-E transient regime where lag is band-aid.
- (refines-v1) **Refit K_us, tau, L_eff jointly per-platform on yaw RMSE** — cheap sanity check.
- (orthogonal) **Blend V1 with a smoothed V0** — `yr = w*v1 + (1-w)*v0_smoothed`; non-structural blend as a sanity-check ceiling.

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
- What I did: ran an inline scoring harness (`out/scoring.py`) on
  `code.v1_baseline.predict_v1` against all of `data/sim-only/segments/`.
- Result (dev pooled, this dataset): yaw 0.01061 rad/s; CTE 75.65 m.
  - Per-platform: Lightning yaw 0.01273 / CTE 62.2 / signed +0.32;
    Mach-E yaw 0.01363 / CTE 98.7 / signed -21.98;
    IONIQ-5 yaw 0.00893 / CTE 69.5 / signed -11.57; Tesla 0/0.
  - Note: numbers differ from AGENTS.md (~half the figures) because this run
    uses the full sim-only set (~3.5M samples) vs the smaller dev slice the
    AGENTS doc was calibrated on. Relative ordering identical.
- Verdict: baseline. Residual diagnosis: large signed CTE drift on Mach-E /
  IONIQ-5 — bias-shaped — plus an |a_lat|-bin-dependent yaw bias on Mach-E
  growing from -0.003 (low a_lat) to -0.012 (3-5 m/s²).

## E01 — V1 + affine post-correction
- Model dir: models/affine-postcorrection/
- Hypothesis: Signed-CTE drift is a single number per platform. A two-param
  per-platform OLS calibration on V1's output should kill most CTE.
- What I changed vs E00: added `yr = a*yr_v1 + b` per platform.
- Result (dev pooled): yaw 0.01061 → 0.01053 (-0.7%); CTE 75.65 → 72.53 (-4.1%).
- Verdict: KEEP.
- Things this rules out: most of the available CTE win is bias-removal, not
  scale or shape. The yaw RMSE moves <1% — residual is dominated by
  high-frequency noise, not structure removable by point-wise calibration.

## E02 — V1 + saturation (cubic in a_lat)
- Model dir: models/saturation-correction/
- Hypothesis: Bin-wise diagnostic showed mean residual growing with |a_lat|
  on Mach-E, suggesting tyre saturation V1's linear K_us misses.
- What I changed: added `c * yr_v1 * (v*yr_v1)^2` to the affine model.
- Result (dev pooled): yaw 0.01053 (~tied); CTE 72.61 (~tied with affine).
- Verdict: SHELVE.
- Things this rules out: a linear-fit single-feature cubic correction cannot
  separate from the affine gain — it co-collapses on lstsq. A real saturation
  attack would need to enter as nonlinear understeer inside V1's steady-state
  equation, not as a residual feature.

## E03 — V1 + residual features (affine + saturation + steering-rate)
- Model dir: models/v1-plus-residual-features/   (SHIPPED)
- Hypothesis: V1's first-order lag is a single-pole approximation of dynamic
  steering response. Adding `d * d(delta_road)/dt` as a residual feature should
  capture transient yaw V1 misses, especially on Mach-E (worst-fitted).
- What I changed: combined OLS over [yr_v1, 1, yr_v1*a_lat², ddelta_dt].
- Result (dev pooled): yaw 0.01052 (-0.9% vs V1); CTE 72.61 (-4.0% vs V1).
- Verdict: SHIP.
- Things this rules out: the steering-rate term has a meaningful Mach-E
  coefficient (-0.022) — real structural signal — but it lifts yaw only ~1 bp
  and CTE not at all beyond the affine bias. The bulk of the gain is the
  per-platform `b` term. The transient-residual story is real but small.
