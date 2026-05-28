# Implement notes — 20260527T135842Z

## Per-variant log

### V0 — baseline KS (clamped v, δ)
- Read `yaw_rate_pred_rads` / `yaw_rate_meas_rads` straight from `sim.csv` (pre-clamped contract).
- RMSE overall = 0.01214 rad/s. Straight 0.00851 (DC bias visible), steady 0.02520, transient 0.04892 (slip).
- Sign sanity: corr(δ_road, ψ̇_meas | cornering) = +0.927 — clean.

### V1 — per-segment IMU bias (estimated on straight only, applied everywhere)
- bias_seg = mean(yaw_meas − yaw_pred_v0) over `|δ|<0.01` rows of that segment (≥20 samples).
- Straight RMSE 0.00851 → 0.00506 (-41%). Hypothesis confirmed: there IS a per-segment DC offset.
- Steady 0.02520 → 0.02602 (+3%), transient 0.04892 → 0.05119 (+5%). Applying the bias correction outside straight slightly degrades cornering — expected when the DC offset is partly a gyro bias and partly straight-segment camber/banking that does not generalise to cornering.
- Net overall: -0.00159 (drop). Net win.

### V2 — linear ST steady-state gain, openpilot prior C_α (with V1 bias)
- `ψ̇ = v·δ / (L·(1+K_us·v²))` with K_us from openpilot prior, KS fallback `v<2 m/s`.
- Prior `K_us = m(l_r·C_αr − l_f·C_αf) / (L²·C_αf·C_αr)` = small positive (Mach-E is mildly understeering by openpilot's prior).
- Straight 0.00506 → 0.00335 (better — at low δ, ST gain ≈ v·δ/L, slightly smaller than (v/L)·tan(δ)).
- Steady 0.02602 → 0.03425 (WORSE +32%). Transient 0.05119 → 0.06367 (WORSE +24%).
- **Regression flag.** Interpretation: openpilot's prior K_us shrinks the predicted ψ̇ relative to KS, but the truth on cornering is closer to (or above) KS — i.e. KS at this `|δ|` is already biased low vs truth, not high. The linear-ST gain in the wrong direction here is consistent with the priors being mis-calibrated for these tyres, or with non-trivial slip-angle contributions that the linear form cannot capture.

### V3 — linear ST, fit K_us by 1D LSQ on steady cornering (scale openpilot C_α ratio)
- Best K_us is **negative** (oversteer-leaning), which when scaling C_α with ratio-preserving inverse, pegs C_α at the lower bound 50_000 N/rad (both front and rear). 
- **C_α pegged at bound 50_000 — regression rung per the skill's discipline (linear-ST form is wrong, not just the priors).**
- Result: RMSE on every regime worse than V2 (overall 0.01550). Reported, not silently buried.

### V4 — ridge residual learner on `[v, |a_y|, |δ|, sign(δ̇)]`, leave-one-segment-out
- λ = 10, intercept un-regularised, per-fold standardisation.
- Recovers some of V2/V3's losses but does not get back below V1 (overall 0.01336 vs V1 0.01055).
- LOSO is the only honest score; in-fold would have been lower but uninformative.

## Deviations from the plan

- None in structure. Three rungs (V2/V3) regressed; reported with physical reasoning per the locked plan's discipline rather than swapping variants.

## Numerical results table (RMSE rad/s, same masks across rungs)

| Variant | overall | straight | steady | transient |
|---|---|---|---|---|
| V0 baseline KS | 0.01214 | 0.00851 | 0.02520 | 0.04892 |
| V1 +IMU bias | 0.01055 | 0.00506 | 0.02602 | 0.05119 |
| V2 +ST prior | 0.01248 | 0.00335 | 0.03425 | 0.06367 |
| V3 +ST fit (pegged) | 0.01550 | 0.00569 | 0.04286 | 0.07162 |
| V4 +ridge LOSO | 0.01336 | 0.00563 | 0.03541 | 0.06249 |

Marginal drops (overall, lock-order): V1 +0.00159, V2 −0.00193, V3 −0.00302, V4 +0.00214.
Sum of marginals = total V0→V4 drop = −0.00122 (consistency 100%).

**Net of the ladder: V4 ends worse than V1.** The honest winner is **V1 alone**: per-segment IMU yaw-gyro bias removal, −13% overall RMSE (−41% straight).

## Things I would change about the harness / data / skills

- Provide a 1-D K_us fit utility in `code/` so V3 isn't bespoke. The 1D grid+golden-section here is fine but every agent will reinvent it.
- A "ST vs KS, which is closer to truth on this corpus" sanity probe before V2 would have caught the prior-direction issue in research, not in implement.
- Banking channel from openpilot's `liveLocationKalman` would let us separate IMU bias from road-camber on straight samples — currently fused into one number.
