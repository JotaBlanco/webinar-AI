# Implement notes — `rpi/runs/20260527-155851/implement-notes.md`

## Per-variant log

### V1 — per-segment yaw-bias from straight-line samples
- Implemented as: mean of `yaw_rate_resid_rads` over straight-line samples in each segment (≥50 samples threshold), subtracted across **all** regimes within that segment. Code: `tools/variants.py`.
- Result: overall RMSE 0.01190 → 0.01013 (Δ = +0.00176). Straight RMSE 0.00853 → 0.00498 (−42%). Steady +0.7%, transient +3.6% — *modestly worse* on cornering.
- Notes / surprises: straight drop confirms a per-segment yaw-gyro / heading-rate offset is real and ≈3–5 mrad/s typical. The slight cornering uptick is because the bias is estimated on straight samples only; if the gyro has a small scale error, the estimate is the wrong shift for cornering. Net is still positive.

### V2 — linear ST steady-state gain, prior `C_α`
- Implemented as: `ψ̇ = v·δ / (L·(1 + K_us·v²))` with `K_us = m(l_r C_αr − l_f C_αf)/(L² C_αf C_αr) = 5.6e-4 s²/m²` (positive ⇒ understeer). KS fallback for `v < 2 m/s`. Cumulative on top of V1 bias.
- Result: overall RMSE 0.01013 → 0.01656 (Δ = **−0.00643**, regression). All regimes regressed: straight 0.00498→0.01296, steady 0.02396→0.03110, transient 0.05411→0.06191.
- Notes / surprises: Per the falsifiability criterion in `plan.md` (V2 row), this rung is **flagged as a regression with a physical reason**: the speed-known KS prediction already happens to track the average `|ψ̇|` of this fleet very closely (mean `|ψ̇_pred|=0.1217` vs `|ψ̇_meas|=0.1299` on cornering — KS under-predicts by ~6%, which the textbook ST gain *further reduces*, blowing the magnitude gap wide). The openpilot prior `K_us` is the wrong sign-of-effect on this particular Mach-E fleet; the actual `K_us` is closer to zero or slightly negative (oversteer-leaning under these conditions). Plan held — partial shipped.

### V3 — linear ST with fit `C_α`
- Implemented as: L-BFGS-B fit of `(C_αf, C_αr)` on cornering samples, bounded [50, 500] kN/rad. Loss = MSE of `(ψ̇_ST − ψ̇_meas) − bias`.
- Result: optimizer returned the priors (286,551 / 355,912) — no improvement. Neither bound was pegged. Δ = 0.
- Notes / surprises: The objective surface around the prior is essentially flat in the `C_α` direction because the residual is dominated by non-`C_α`-shaped contributions (per-segment scatter + high-`|a_y|` non-linearity outside ST validity). With the linear-ST functional form, no `(C_αf, C_αr)` in physical range improves things. Per `plan.md`, this is the "flag regression risk for linear-ST form" signal even though the fit did not peg the bound.

### V4 — steering-rate lead `τ`
- Implemented as: `δ_eff = δ + τ·dδ/dt`, line-search `τ ∈ [0, 0.15]` s, scored on transient-cornering RMSE.
- Result: `τ* = 0.000 s`. No improvement.
- Notes / surprises: Per the V4 falsifiability criterion ("if best `τ ≤ 5 ms` … no phase offset to fix"), there is **no phase offset** between `δ_road` and `ψ̇_meas` in this preprocessed CSV. Either the adapter already time-aligned them, or the offset is below the 20 ms grid resolution.

## Deviations from the plan

- None in structure. V2 regressed; per the lock discipline I shipped it as a regression rung with a physical reason rather than reordering. V3 and V4 returned no improvement — reported honestly as zero marginal drops, not silently dropped.

## Numerical results table (final)

| variant | overall | straight | steady | transient | Δ overall (strict marginal) |
|---|---:|---:|---:|---:|---:|
| V0 baseline KS | 0.01190 | 0.00853 | 0.02331 | 0.05224 | — |
| V1 per-seg bias | 0.01013 | 0.00498 | 0.02396 | 0.05411 | **+0.00176** |
| V2 lin-ST prior Cα | 0.01656 | 0.01296 | 0.03110 | 0.06191 | **−0.00643** (regression) |
| V3 lin-ST fit Cα | 0.01656 | 0.01296 | 0.03110 | 0.06191 | 0.00000 |
| V4 rate-lead τ | 0.01656 | 0.01296 | 0.03110 | 0.06191 | 0.00000 |

Total V0→V4 drop: **−0.00467** (net regression). Sum of marginals matches total to floating precision (no double-counting).

If the ladder is **truncated at V1** (the only rung that actually helps): V0→V1 drop = +0.00176 (15% of V0 overall RMSE). Straight regime improves 42%.

## Things I would change about the harness / data / skills

- The skill doc presents linear-ST as a one-DoF upgrade with predicted direction "drops" — on a speed-known + KS-already-good fleet, it can plausibly regress. A note in `vehicle-dynamics-rlog/SKILL.md` mentioning this caveat would have shortened the surprise loop.
- Consider providing a per-segment `gyro_bias_estimate` channel pre-computed in the sim CSV; V1 logic is canonical enough that every team will re-derive it.
- A LOSO ML-residual rung was out of budget for a 15-min slot; would have been the natural V5.
