---
name: f150-yaw-ceiling
description: Per-platform plateau every cohort has hit. F150 yaw sits flat at ~+21% across 90 agents in m3.v2 / m3.v3 / m4.v1 / m4.v2. Documented here so v2.01 agents stop burning budget on rung-0 F150 tweaks and reach for M3 (double-track + load transfer) instead.
when-to-load: When your residual diagnostic shows F150 dominating the pooled-yaw error. Or before you start any "let me retune V1 on F150" tangent.
load-cost: ~400 words.
---

# The F150 yaw-rate ceiling

## The number

Across **90 agents** in m3.v2 / m3.v3 / m4.v1 / m4.v2 — every published
final-model graded via canonical eval against the same val pool —
**FORD_F_150_LIGHTNING_MK1 yaw-RMSE improvement clusters tightly around
+21% ± 2.5% vs V0**. Median 22.4%. The platform pulls the pooled
headline down despite Mach-E and Ioniq individually improving at +55–57%.

This is not a skill gap. It is not solved by another round of rung-0
coefficient tuning. The cohort tried that ninety times.

## What the failure looks like

If you run `score-model` on V1 against F150 you'll see the residual
concentrated in:

1. **Highway sweepers** (`v > 25 m/s`, `|a_lat| ∈ [2, 5]`) — the model
   predicts more yaw than the truck delivers. F150 understeers more at
   speed than V1's steady-state `K_us` captures.
2. **Body-roll-coupled transitions** — quick left-right inputs where
   the truck's high CG and tall sidewalls delay the lateral response.
3. **Per-segment residuals are biased**, not noisy — `bias_warnings`
   often lights up on F150 for systematic yaw drift, which is what
   ultimately blows CTE on long routes.

## The physics hypothesis

F150 Lightning is **3084 kg with h_cg ≈ 0.74 m and l_f / l_r ≈ 0.44 /
0.56** — heavy, high CG, rear-biased weight distribution. Two things V1
cannot represent:

- **Lateral load transfer** at sustained `a_lat`. The outer tires carry
  much more load → `C_α` effectively shifts because tire stiffness
  saturates nonlinearly with `F_z`. Steady-state understeer `K_us` is
  a single scalar; the truck needs the per-axle load-transfer effect.
- **Per-axle nonlinear tire response.** With `F_z` shifted, the inner
  tire can hit Fiala saturation while the outer tire stays linear. The
  axle-averaged linear-tire model in V1 misses this.

## What probably works (and is prefilled)

**M3 — Double-track with lateral load transfer** at
`phases/3-implement/models/m3-double-track-load-transfer/` is the
physics targeted at exactly this failure mode. It models four wheels
with per-wheel `F_z` from a quasi-static lateral-load-transfer formula,
then `F_y` per wheel from Fiala. Initial coefficients are F150
carParams; the fit harness tunes `μ`, `C_α` per axle, and `h_cg / t_w`.

**M2 — Fiala tire** alone (no double-track) may also help, since the
saturation onset matters more than the per-wheel split if `a_lat`
isn't too high. Run M2 first as a cheaper sanity check; if it doesn't
help F150 substantially, climb to M3.

**What likely won't help**: M4 (relaxation-length) targets transient
phase lag, which is a Mach-E story, not an F150 one. M5 (friction
circle) targets long-lat coupling, which would help in brake-in-corner
routes; mixed signal on F150 — try if your residual is concentrated in
braking segments.

## What's definitely not the answer

- Re-tuning V1's `K_us` on F150-only data. m3.v3, m4.v1, m4.v2 all
  tried; the gain is ≤ 1 percentage point at best.
- Per-segment δ₀ on F150. Lightning uses a global δ₀ for a reason
  (see `references/anti-patterns.md`).
- Fitting `tau` more carefully. The lag is small on F150; refining
  it doesn't move the headline.

## Honest disclaimer

It's possible the floor is **data quality**, not model class. The
Lightning rlogs are smaller-N than the other platforms and the carParams
mass/inertia values are the OE static values — actual loaded mass on
the day depends on payload. If M3 + M2 still don't budge the ceiling,
the next move is a data audit (`skills/inspect-residuals` per route),
not a sixth rung.
