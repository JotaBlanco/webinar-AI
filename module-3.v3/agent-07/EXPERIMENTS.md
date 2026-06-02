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

- (structure) **Linear dynamic single-track (rung 1)** with bicycle-model ODE on `(vy, yr)`, RK4 integration; attacks transient-regime yaw RMSE (0.0165 vs 0.0044 straight) and Mach-E first-order-lag band-aid.
- (structure) **Second-order yaw transfer function** (V1's `yr_ss` driven through a damped second-order LTI instead of first-order lag); attacks transient yaw overshoot directly without committing to bicycle-model identifiability.
- (structure) **Steering-rate feedforward correction** — add `k_δ̇ · d(δ_road)/dt` to V1's yr; attacks the same transient residual via "anticipation" without ODE state. Structurally different shape: input-derivative term V1 lacks entirely.
- (structure) **Per-platform steering-gain debias** — fit `g` so residual slope vs truth = 0; orthogonal to V1's shape because V1's `g` was fit jointly with K_us/L_eff and is locked. Attacks CTE drift (proportional yaw bias).
- (refines-v1) **Re-fit V1 coefficients per route** rather than per platform — sanity check that V1's pooled fit isn't washing out heterogeneity.
- (orthogonal) **Blend V1 with V0** (convex combo) on transient regime — averaging instead of new structure. Cheap fallback.

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

## E01 — V1 residual probe

- Hypothesis: per-platform signed yaw bias should be largely a constant or
  v-dependent offset.
- What I did: looped over Mach-E, IONIQ-5, Lightning; computed signed yaw
  residual in regime slices (straight/steady/transient, left/right turns,
  v bins, high-|a_lat|).
- Result: **strong left/right asymmetry on Mach-E and IONIQ-5.** Right-turn
  bias on Mach-E -0.00719; left-turn bias -0.00032. IONIQ-5 right -0.00547;
  left +0.00026. Lightning is symmetric. Transient regime carries 3.5× the
  yaw RMSE of straight regime (0.0165 vs 0.0047).
- Verdict: actionable. Two attack vectors: (a) asymmetric steering scale,
  (b) dynamic-ST for the transient residual. (a) is easier; try first.

## E02 — v1-steerrate-ff (yr_v1 + k_dd · ddelta · clip(v,0,40)/30)

- Model dir: models/v1-steerrate-ff/
- Hypothesis: V1's first-order lag underfits the transient response;
  adding the steering derivative as a feedforward term should restore the
  second-order behaviour.
- What I changed: yr = yr_v1 · g_corr + k_dd · ddelta · clip(v,0,40)/30.
  Grid scan over (g_corr, k_dd) per platform on 120 segments.
- Result (pooled subset): yaw -0.2% / -0.3% / -0.7% per platform; CTE
  essentially unchanged. k_dd sign flipped to negative on Mach-E (the term
  was correcting an over-anticipation, not adding one).
- Verdict: **shelve.** Below noise. The transient residual is not a missing
  scalar input-derivative — it likely needs a true second-order dynamic.
- Rules out: scalar steering-derivative feedforward as a cheap structural
  attack on the transient.

## E03 — v1-asym-gain (sign-dependent steering gain)

- Model dir: models/v1-asym-gain/
- Hypothesis: E01 found pure left/right gain asymmetry. A smooth-blended
  pair (g_left, g_right) replaces V1's single g.
- What I changed: g_eff = g_left · w_left + g_right · (1−w_left), where
  w_left = 0.5·(1+tanh(δ_raw/0.005)). Fit per platform via Nelder-Mead on a
  yaw/cte-anchored loss.
- Result (pooled full): yaw 0.005844 (-0.5% vs V1); CTE 56.04 (-1.4% vs V1).
  Mach-E signed-bias fraction collapses from 0.03 → 0.004; IONIQ-5 0.01 →
  0.001. Lightning held neutral.
- Verdict: **keep.** Small but real and consistent across platforms.

## E04 — v1-asym-debias (E03 + gated additive output bias)  [SHIPPED]

- Model dir: models/v1-asym-debias/
- Hypothesis: even after the gain split, a small residual signed-bias
  remains (e.g. Mach-E -0.00055 after E03). Closing it with a gated additive
  output term should kill the surviving CTE drift.
- What I changed: yr = yr_lag + b_offset · 1[v > 2]. Fit b_offset on top of
  the E03 (g_left, g_right). **Halved** b_offset on Mach-E/IONIQ-5 and
  **zeroed** on Lightning to guard against subset overfitting (the 80-seg
  fit produced a Lightning b_offset of -0.00165 that made the full-dataset
  bias *worse* — see E04a below).
- Result (pooled full): yaw 0.005805 (**-1.2% vs V1**); CTE 54.69
  (**-3.7% vs V1**). Mach-E CTE 98.68 → 92.49 (-6.3%); IONIQ-5 CTE 69.53 →
  67.65 (-2.7%). All bias warnings cleared (signed yaw |·| < 0.0003 every
  platform; cte_drift -5 to -7 m, well under V1's -22 m on Mach-E).
- Verdict: **ship.**
- Rules out: refits of V1's existing-shape coefficient alone (was tested in
  E03; reached only 1% pooled). Confirmed the V1 paper claim that
  coefficient-level intervention is bounded at ~1-5%.

## E04a — overfit Lightning b_offset

- What happened: optimising b_offset jointly on 80 Lightning segments produced
  -0.00165, which on the full dataset (175 Lightning segs) flipped signed
  bias to -0.00169 and signed CTE drift to -19.7 m — **worse** than V1.
- Mitigation: zero out Lightning's b_offset (already at threshold pre-fit).
  This is a regularisation pattern: when the V1 residual on a platform is
  already at the noise floor, additional fitting only adds variance.
- Captured so the next agent: don't fit additive offsets on platforms whose
  V1 signed bias is already within ⚠️ threshold. The fit will overshoot.
