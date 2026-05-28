# Implement notes

Tool: `tools/run_ladder.py`. Run as `python3 tools/run_ladder.py <PLATFORM>`.

Order matched the plan: V0 → V1 → V2 → V3, per-platform fits on TRAIN, scored on TEST. Same interleaved (idx % 5 == 0) test mask and same regime mask across all variants (rule 11).

## Deviation 1 — V2 regression-direction bug, caught and fixed
First pass used `pred_v2 = (pred_v1 − a)/b` (inverting the regression). That made V2 WORSE — overall +0.0026 rad/s on Mustang. The fit was `meas ≈ a + b·pred`, so the best estimator of meas given pred is `pred_v2 = a + b·pred_v1`, not the inverse. Fixed and re-ran. This is the bug rule 1 warns about; logging it here in case it bites someone again.

## Deviation 2 — V3 understeer-gradient is null
On both platforms `K ≈ 0` after V2. The kinematic-vs-truth mismatch is dominated by a per-platform scalar gain (V2's `b`), not a velocity-squared term. V3 is reported but the falsifier triggered: K is ~0 and contribution to overall RMSE is ≤ 1e-5. Hypothesis rejected, partial shipped per the honesty contract.

## Deviation 3 — V1 contribution is null on Mustang
Mustang `bias = +0.0011 rad/s` — well below the straight-line noise floor (~0.0088). Δoverall = −2e-5. Not worth keeping as a separate rung but kept for accounting transparency. On F-150 the bias is +0.0046, larger but still small.

## Surprise — gain sign flips across platforms
- Mustang Mach-E: `b = 1.094` → kinematic prediction *undershoots* truth by ~9%.
- F-150 Lightning: `b = 0.867` → kinematic prediction *overshoots* truth by ~13%.

Cannot be patched with a single global gain. Most likely cause is per-platform `i_s` (steer ratio) error or tyre-compliance-induced effective wheelbase. Mustang `i_s=17.0`, F-150 `i_s=16.9` — close in the dict, but the *effective* ratio (accounting for rack compliance) clearly differs and in different directions. Worth a follow-up.

## Final numbers — V0 vs best (V2 = V3 within rounding) on TEST

Mustang Mach-E (per-platform fit):
- overall  0.01613 → 0.01597 (−0.00016, −1.0%)
- straight 0.00878 → 0.01043 (+0.00165, **REGRESSION**)
- steady   0.03147 → 0.02952 (−0.00195, −6.2%)
- transient 0.05743 → 0.05013 (−0.00730, −12.7%)

F-150 Lightning (per-platform fit):
- overall  0.02037 → 0.01643 (−0.00394, −19.3%)
- straight 0.00899 → 0.00664 (−0.00235, −26.1%)
- steady   0.03629 → 0.02865 (−0.00764, −21.1%)
- transient 0.05161 → 0.04472 (−0.00689, −13.3%)

## Straight-line regression on Mustang — physical cause
V2 applies `pred_v2 = a + b·pred_v1` everywhere. On straights, `pred_v1 ≈ 0` so `pred_v2 ≈ a = +0.004 rad/s`. That intercept is meaningful in cornering but uncorrelated with the straight-line residual. Either gate V2 by `|δ|≥0.01` (apply gain only in cornering) or fit a zero-intercept model on cornering and re-bias on straights. Not done here to keep the variant count locked.

## Schema check
Re-emitted `out/<PLATFORM>/sim_v3.csv` for the first segment of each platform.
- `out/FORD_MUSTANG_MACH_E_MK1/sim_v3.csv` — `evals/schema_check.py` → PASS
- `out/FORD_F_150_LIGHTNING_MK1/sim_v3.csv` — `evals/schema_check.py` → PASS

Residuals are `pred − meas` and `a_y_pred = v · ψ̇_pred` (rule 9). NaN-free.

## Artifacts
- `out/FORD_MUSTANG_MACH_E_MK1/ladder_test_rmse.csv`
- `out/FORD_MUSTANG_MACH_E_MK1/fit_params.txt`
- `out/FORD_MUSTANG_MACH_E_MK1/sim_v3.csv`
- `out/FORD_F_150_LIGHTNING_MK1/ladder_test_rmse.csv`
- `out/FORD_F_150_LIGHTNING_MK1/fit_params.txt`
- `out/FORD_F_150_LIGHTNING_MK1/sim_v3.csv`
