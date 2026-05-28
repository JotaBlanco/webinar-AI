# Module-4 / agent-01 (angle-B) — Lateral fidelity ladder

## Headline

On 60 Mach-E segments (~180k samples at 50 Hz) of clamped-(v,δ) KS, the honest win is **V1 per-segment IMU yaw-gyro bias removal: -13% overall RMSE (0.01214 → 0.01055 rad/s), -41% on straight (0.00851 → 0.00506)**. Every rung above V1 regressed; the ladder's net V0→V4 drop is **negative** (-0.00122). Shipping the partial and reporting the regression flags rather than swapping variants.

## Platform / contract

Ford Mustang Mach-E MK1 (the only platform with truth ψ̇ and a_y; Tesla has no IMU truth). `v` and `δ` clamped to measured; residual under test is `yaw_rate_pred_rads − yaw_rate_meas_rads`. Sign sanity passed: `corr(δ_road, ψ̇_meas | cornering) = +0.927`.

## Variant ladder (same segments, same mask, RMSE rad/s)

| # | Variant | overall | straight | steady | transient | marginal Δ overall |
|---|---|---|---|---|---|---|
| V0 | baseline KS | 0.01214 | 0.00851 | 0.02520 | 0.04892 | — |
| V1 | + per-seg IMU bias | **0.01055** | **0.00506** | 0.02602 | 0.05119 | **-0.00159** |
| V2 | + linear ST, prior C_α | 0.01248 | 0.00335 | 0.03425 | 0.06367 | +0.00193 (regress) |
| V3 | + linear ST, fit C_α | 0.01550 | 0.00569 | 0.04286 | 0.07162 | +0.00302 (regress, **C_α pegged at lower bound 50 kN/rad** — linear-ST form is wrong, not just priors) |
| V4 | + ridge residual, LOSO | 0.01336 | 0.00563 | 0.03541 | 0.06249 | -0.00214 (recovers some V2/V3 loss but never beats V1) |

Marginal drops sum to total V0→V4 (consistency 100%, lock-order strict-marginal).

## Painful absence

No banking/camber channel. The per-segment "bias" V1 removes is a mix of true IMU offset and steady road-camber on straight stretches; that's why applying V1 outside straight nudges cornering RMSE up +3-5%.

## Near-miss

V2 wins **on straight** (-34% vs V1) because at small δ the ST gain is slightly smaller than KS's `tan(δ)/L`. But V2 ships KS-truth divergence in the wrong direction on cornering — the openpilot prior K_us shrinks ψ̇ when truth is, if anything, **above** KS. V3 confirms it: 1-D fit drives K_us negative (oversteer-leaning) and pegs both C_α at the 50 kN/rad floor.

## Surprise

The cleanest, cheapest fix is also the only fix that worked: 1 scalar per segment. The whole tyre-model rung is mis-pointed on this prior set; before any honest ST rung, a **direction-of-K_us probe** belongs in Research, not in V2.

## RPI artifacts

- Research: `rpi/runs/20260527T135842Z/research.md`
- Plan (locked): `rpi/runs/20260527T135842Z/plan.md`
- Implement notes: `rpi/runs/20260527T135842Z/implement-notes.md`
- Numerical artifact: `out/ladder.json`
- Tool: `tools/lateral_ladder.py`
