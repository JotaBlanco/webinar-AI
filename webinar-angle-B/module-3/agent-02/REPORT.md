# Module-3 / agent-02 (angle-B) — Lateral fidelity ladder (Mach-E)

## Headline

**Platform: FORD_MUSTANG_MACH_E_MK1** (315 segments, ~9.4 M samples at 50 Hz). Speed-known, lateral-only contract: `v` and `δ` clamped to measured; the model predicts `ψ̇`. Scored against `yaw_rate_meas_rads`. Sign sanity `corr(δ_road, ψ̇_meas | cornering) = +0.702` — convention OK.

## Variant ladder

Yaw-rate RMSE (rad/s), same segments, same regime mask:

| Variant | Name | all | straight | steady | trans | marginal Δ |
|---|---|---:|---:|---:|---:|---:|
| V0 | KS, as shipped | 0.0161 | 0.0088 | 0.0317 | 0.0569 | — |
| V1 | V0 + per-seg straight-line yaw bias removal | 0.0147 | 0.0049 | 0.0317 | 0.0574 | -0.0014 |
| V2 | Linear ST, prior C_α (+ V1 bias) | 0.0155 | 0.0034 | 0.0343 | 0.0629 | +0.0008 (regression) |
| V3 | Linear ST, fit C_α (bounded 50–500 kN/rad) | 0.0151 | 0.0034 | 0.0333 | 0.0616 | -0.0004 |
| V4 | V3 + Ridge residual learner, **LOSO CV** | 0.0149 | 0.0035 | 0.0329 | 0.0604 | -0.0002 |

Total V0 → V4 drop = **0.0012 rad/s (7.5%)**. Sum of marginal drops = 0.0012 — within-15% reconciliation passes. Accounting scheme: **ladder-order marginal**.

V3 fit: `C_αf = 158 261 N/rad`, `C_αr = 138 286 N/rad` — both well inside physical range, **much softer than openpilot priors** (286.5k / 355.9k). Not pegged at any bound.

## Painful absence

Almost all available headroom lives in V1 (a per-segment yaw-gyro bias, not a model upgrade). The fancy stuff — ST priors, fit C_α, residual learner — together adds **0.0002 rad/s** on top of V1. The team's KS-vs-ST debate is being held about a 1.5% effect; the real win is an IMU offset correction that any rung can absorb.

## Rule-prevented near-misses

- Skill warned not to score Tesla (no truth) → used Mach-E.
- Skill warned `delta_wheel_deg` vs `delta_road_rad` (factor-15 trap) → consumed `delta_road_rad`.
- Ladder discipline forced LOSO CV on V4; in-fold Ridge would have spuriously closed the residual.
- Same segment set + same regime mask across rows → marginal-drop sum reconciles.

## Honest regression flag

**V2 regresses against V1 on cornering** (steady 0.0317 → 0.0343, transient 0.0574 → 0.0629). Physical reason: openpilot prior C_α is too stiff for these tyres / pavement; linear-ST steady-state gain under-rotates the yaw response. V3 confirms by fitting softer stiffnesses (~55% of prior front, ~39% of prior rear) and partially recovering — but not enough to beat V1's gyro-bias correction on its own.

## Surprise

On this dataset, **KS is not the lateral problem**. The dominant error in lateral fidelity is a static per-segment yaw-rate bias (likely IMU gyro offset accumulating), not the missing slip in the kinematic model. Climbing the CommonRoad fidelity ladder past KS pays diminishing single-digit-percent dividends until tyre slip starts dominating, which on this segment mix it does not. The C_α fit being substantially softer than openpilot's prior is a quiet finding: the canonical numbers under-predict actual yaw gain at modest steering inputs.

Files: `out/ladder.json`, `tools/lateral_ladder.py`.
