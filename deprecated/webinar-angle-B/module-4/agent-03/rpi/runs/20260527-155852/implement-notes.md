# Implement notes — `rpi/runs/20260527-155852/implement-notes.md`

Code: `tools/run_ladder.py`. Output: `out/ladder.csv`. Run on 80 Mach-E segments (deterministic stride from 315), 203 303 samples after `v ≥ 2 m/s`.

## Run output (yaw-rate-residual RMSE, rad/s)

| Variant                  | overall | straight | steady  | transient | marginal drop |
|--------------------------|---------|----------|---------|-----------|---------------|
| V0_baseline              | 0.01451 | 0.00890  | 0.02706 | 0.04893   | —             |
| V1_bias_per_seg          | 0.01262 | 0.00474  | 0.02673 | 0.04884   | **+0.00189**  |
| V2_ST_prior_Calpha       | 0.02035 | 0.01415  | 0.03652 | 0.06065   | **−0.00773** (regression) |
| V3_ST_fit_Calpha_LOSO    | 0.02188 | 0.01787  | 0.03360 | 0.05538   | **−0.00153** (regression) |
| V4_Ridge_residual_LOSO   | 0.02143 | 0.01836  | 0.03004 | 0.05168   | +0.00045      |

Total V0→V4 overall drop: −0.00692 (i.e. V4 is *worse* than V0 by ~48%).
Sum of marginals = total exactly (no drift; strict marginal in fixed order).

## What happened, variant by variant

- **V1 worked as predicted.** Straight-regime RMSE collapsed from 0.0089 to 0.0047 (≈47% drop). Steady and transient barely move (-0.0003, -0.0001) — consistent with a per-segment additive bias, not a regime-dependent fix. This is the only honest win in the ladder.
- **V2 regressed**, exactly as the plan warned. Replacing `(v/L)·tan(δ)` with the SS-ST gain at openpilot's prior `C_α` *over*-states understeer for this car; predicted yaw rate becomes ~30% too small at typical cornering speeds. ST also picks up speed-dependent error on the straight regime (where the geometric KS prediction is tiny but ST gain v·δ/L·(1+K_us·v²) still drifts vs measured residual offset). Note the V1 IMU-bias correction is *cumulatively* applied — V2's straight-regime RMSE is not the bare ST result, it's ST + V1 bias soak.
- **V3 LOSO fit went the wrong way.** Median fit `C_αf = 394 486`, `C_αr = 257 100` (compare priors 286 551 / 355 912). The fit *inverted* the front/rear stiffness ratio to *reduce* understeer, but the resulting ST gain is still further from truth than KS's geometric prediction. `C_αf` clustered at 392–400 kN/rad across folds — close to but not pegged at the 500 kN/rad upper bound (raised from default 500k in the code). **Soft regression flag**: stiffness sits in the upper-physical band, indicating the linear-ST steady-state form is misspecified, not just its priors. The data is calling for either (a) yaw-rate transient dynamics (linear-ST *dynamic*, not steady), or (b) a non-linear tyre.
- **V4 Ridge residual learner** clawed back only 0.00045 of V3's mess — `[v, |a_y|, |δ|, sign(δ̇)]` cannot recover from a misspecified steady-state ST baseline through a linear fit. LOSO disciplined the score, so this is not an in-fold artefact.

## Deviation from plan

- None in *what* was run. The plan locked, the ladder ran in order, every variant was scored on the same sample set and regime mask. The plan *predicted* a possible V2 regression and that is what occurred; per attribution discipline, V2/V3/V4 are reported as written rather than re-ordered or dropped.
- One mid-run bug fix to V1 before the locked run produced the final numbers: an early V1 prototype subtracted `mean(yaw_rate_meas | straight)` instead of `mean(yaw_rate_resid_v0 | straight)`. The former subtracts real curvature traversed during straight intervals; the latter subtracts only the gyro bias. Fixed before the final ladder.csv was written. Diary kept.

## Files

- Code: [tools/run_ladder.py](../../../tools/run_ladder.py)
- Output: [out/ladder.csv](../../../out/ladder.csv)
