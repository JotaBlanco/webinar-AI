# Plan — `rpi/runs/20260527-155852/plan.md`

Locked at: 2026-05-27 15:58:52. Order is fixed; if a row regresses, ship the partial and note the deviation. Attribution = strict marginal in this fixed order.

## Variant ladder

| # | Variant | Physical hypothesis | DoF added | Predicted direction | Falsifiable success criterion |
|---|---------|---------------------|-----------|---------------------|-------------------------------|
| V0 | baseline | `yaw_rate_resid_rads` as-is | 0 | reference | none — reference |
| V1 | per-segment IMU yaw-gyro bias | Each segment has a constant gyro offset; KS predicts ~0 on straight samples, so `mean(resid_v0 \| straight)` *is* the bias | 1 per segment | overall RMSE drops; straight regime drops most | If straight-regime RMSE does not drop, the "bias" was not a bias (e.g. it was banking) and V1 did not address what I claimed |
| V2 | linear ST steady-state gain, openpilot prior `C_α` | KS misses slip; replace `(v/L)·tan(δ)` with `v·δ / (L·(1 + K_us·v²))` using prior `C_αf, C_αr` | 0 (priors fixed) | drops on steady & transient cornering; tiny straight effect | If steady-regime RMSE does not drop vs V1, prior `C_α` are wrong for this tyre/road and the linear-ST *form* might still be salvageable in V3 |
| V3 | linear ST, fit `C_α` LOSO | Re-fit `(C_αf, C_αr)` on cornering samples, leave-one-segment-out | 2 (bounded 50–500 kN/rad) | drops on steady cornering vs V2; transient still dominated | If LOSO `C_α` peg at a bound, the linear-ST form is misspecified, not just the priors — regression flag, do not advance to V4 with false confidence |
| V4 | Ridge residual learner, LOSO | Whatever lateral fidelity gap remains is correlated with `[v, \|a_y\|, \|δ\|, sign(δ̇)]` | 4 features, α=1 | drops on transient cornering most | If V4 only helps in-fold, do not claim it; LOSO is the honest scorer |

## Attribution scheme

- Strict marginal, fixed order V0→V4. Marginal of V_k = `RMSE(V_{k-1}) − RMSE(V_k)` (overall). Marginals sum to total V0→V4 drop within 15%. Each variant's effect is attributed *to the variant that added that degree of freedom*, not to a re-ordered or best-fit subset.

## Regime mask (fixed, applied identically to every variant)

- straight:  `|delta_road_rad| < 0.01`
- steady:    `|delta_road_rad| ≥ 0.01` and `|dδ/dt| < 0.05 rad/s`
- transient: `|delta_road_rad| ≥ 0.01` and `|dδ/dt| ≥ 0.05 rad/s`

## What would invalidate this plan

- A sign-convention failure on cornering correlation (would force a sign flip before any variant runs). *(Did not occur — corr was +0.934.)*
- LOSO `C_α` pegging at the bound (a regression flag per the skill; V4 then "launders" a misspecified V3).
- V2 *regressing* RMSE vs V1 (would mean steady-state ST with sensible priors is the wrong upgrade direction; flag and continue per attribution discipline).
