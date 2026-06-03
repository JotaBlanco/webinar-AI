# REPORT — final-model/ — agent-11 (m4.v2.01)

This bundle ships **v1-loadtransfer-correction**: V1 baseline with a
per-platform multiplicative correction in the V1 lateral-acceleration
proxy a_lat = yr_v1 * v. Coefficients (k1, k2) fitted per platform on
the frozen train split.

## Headline

| Split | yaw RMSE | CTE RMSE | vs V1 |
|---|---|---|---|
| Dev  | 0.007021 | 69.430 | yaw -0.38%, CTE -0.74% |
| Test | 0.007159 | 65.690 | yaw -0.39%, CTE -0.55% |

Per platform on dev (V1 → SHIPPED):
- FORD_F_150_LIGHTNING_MK1:  yaw 0.00754 → 0.00751,  CTE 93.77 → 90.62 (**CTE -3.4%**)
- FORD_MUSTANG_MACH_E_MK1:   yaw 0.00827 → 0.00818,  CTE 63.65 → 63.45
- HYUNDAI_IONIQ_5:           yaw 0.00650 → 0.00650,  CTE 67.17 → 67.17 (identity)

## Fitted coefficients
- F150:    k1 = -0.00331,  k2 = -0.00063
- MachE:   k1 =  0.00179,  k2 = -0.00271
- Ioniq:   k1 = 0, k2 = 0  (V1 verbatim — train residual not correlated with V1 a_lat)

## Why this is rung 1
The correction introduces a yaw-dependence on the previous yaw output —
specifically a polynomial in V1's lateral-accel proxy. That is the
leading-order coefficient of M3's double-track load-transfer effect on
the equivalent linearised single-track. It is structurally distinct
from V1 (V1 is yr_v1 only); a downstream M3 fit would use these k1/k2
as warm-start priors.

## Why it generalises
The 2-parameter correction has the right capacity for ~100-500 train
segments per platform; held-out test scores match dev signs (cohort
folklore: F150 ceiling looks dev-only, but the load-transfer correction
is a real platform-stable signal because the correlation between V1's
predicted a_lat and the V1 residual is route-invariant in a way that
dev-fit δ₀ tweaks are not).

## Files in this bundle
- `predict.py` — self-contained 8-col contract; reads no external files.
- `manifest.json` — fitted coeffs, dev/test metrics.
