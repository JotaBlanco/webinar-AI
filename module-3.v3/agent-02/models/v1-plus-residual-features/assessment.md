# Assessment — v1-plus-residual-features

## Local dev scores (sim-only/segments/)

| platform | yaw RMSE | CTE RMSE | signed CTE mean |
|---|---|---|---|
| Lightning | 0.01269 (-0.3%) | 62.25 (-0.1%) | -3.80 |
| Mach-E    | 0.01340 (-1.7%) | 91.65 (-7.1%) | -1.84 |
| IONIQ-5   | 0.00889 (-0.4%) | 67.59 (-2.8%) | -4.20 |
| **POOLED** | **0.01052 (-0.9%)** | **72.61 (-4.0%)** | — |

V1 reference pooled: yaw 0.01061, CTE 75.65.

## Residual character
- Signed CTE drift slashed (Mach-E -22 → -1.84 m; IONIQ-5 -12 → -4.20 m).
- The steering-rate coefficient `d` is the largest meaningful structural
  contribution beyond the bias — Mach-E d=-0.022 represents real transient
  modelling that V1's single-pole lag misses.
- Yaw RMSE moves are small because most yaw residual is genuine noise floor.

## Verdict: SHIP. Marginally best on pooled metrics; structurally most
different from V1; the steering-rate feature is a real (small) signal that
affine alone can't catch.

## What's not attacked
- High-frequency yaw noise (probably IMU + numerical-diff noise) — would
  need a proper Kalman filter; out of scope.
- Tesla — no truth, V0 passthrough.
- Rare extreme-|a_lat| transients where V1's understeer saturates — the
  cubic correction is too weak; a true dynamic single-track ODE would help.
