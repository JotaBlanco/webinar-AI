# final-model REPORT — v1-asym-debias

See agent-root REPORT.md for the full agent report. This file is the per-bundle
copy required by preflight.

## Pooled (full dev set)

| metric | V1 | shipped | Δ |
|---|---|---|---|
| yaw_rate_rmse (rad/s) | 0.005874 | 0.005805 | -1.2% |
| cte_rmse (m)          | 56.807   | 54.689   | -3.7% |

## Shape

V1 (kinematic ST + understeer + first-order lag + per-segment δ₀) extended with:
- direction-asymmetric steering gain g_left, g_right (smooth tanh blend at δ=0)
- gated additive yaw-bias offset b_offset, zeroed on Lightning by design

Tesla: V0 passthrough (no truth channel).

## Structural diff vs V1

V1 has a single scalar gain `g`; this candidate makes gain sign-dependent —
not reachable by re-tuning V1's coefs. The additive bias is applied after the
lag, which is a different transfer function from V1's input-side δ₀.
