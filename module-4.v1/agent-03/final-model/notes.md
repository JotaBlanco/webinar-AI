# final-model — v1-plus-per-platform-bias-correction

**Rung**: orthogonal (post-V1 additive correction, not a new physics model)
**Parent**: V1 (`code/v1_baseline.py`)

## What this differs from

Differs from V1 in exactly one way: after V1 produces `yaw_rate_pred_rads`,
a per-platform low-rank correction is added. No change to V1's understeer,
lag, or per-segment delta0 logic.

Per-platform correction (chosen by 5-fold route-grouped CV on
`data/sim/segments`, picking the lowest-rank correction that improves at
least one KPI without regressing the other):

| Platform                  | Correction          | Coeffs                      |
|---------------------------|---------------------|-----------------------------|
| FORD_MUSTANG_MACH_E_MK1   | scale+bias affine   | a=+1.696e-3, b=0.97463      |
| HYUNDAI_IONIQ_5           | linear-in-velocity  | c0=2.231e-4, c1=2.789e-5    |
| FORD_F_150_LIGHTNING_MK1  | scalar scale only   | s=0.98734                   |
| TESLA_MODEL_3             | V0 passthrough      | (no truth channel)          |

## CV result (per-platform, 5-fold route-grouped on data/sim/segments)

| Platform | yaw V1    | yaw post  | Δyaw   | cte V1 | cte post | Δcte    |
|----------|-----------|-----------|--------|--------|----------|---------|
| Mach-E   | 0.013633  | 0.013525  | -0.79% | 98.68  | 91.83    | -6.94%  |
| IONIQ-5  | 0.008933  | 0.008908  | -0.28% | 69.53  | 67.28    | -3.23%  |
| Lightning| 0.012733  | 0.012721  | -0.10% | 62.18  | 61.93    | -0.41%  |

## In-sample (full data/sim/segments) pooled

V1 pooled:    yaw=0.010612, cte=75.65
Final pooled: yaw=0.010535, cte=72.24  (-0.73% yaw, -4.51% CTE)

## What was tried and rejected

- **Ridge residual head** (11 features incl. delta, v, delta·v, ddelta·v, a_lat
  proxy, brake) — regressed CTE on Mach-E (+2.6-5.1%) and IONIQ-5 (+4.7-8.3%)
  in CV. Cohort §4 predicted this would win; it didn't on this CV split. Likely
  because V1 here is *already* the m3.v3+ V1 with per-segment delta0, so the
  remaining residual structure is dominated by a near-constant bias and a
  small scale — not the rich feature interactions a ridge head exploits.
- **Linear bias for Lightning** — confirmed cohort §2 (Lightning at noise
  floor; bias correction regresses).
- **Bias-only for Mach-E** — slightly worse than scale+bias (-6.95% vs -6.94%
  CTE, but scale+bias additionally hits -0.79% yaw vs -0.65%). Used scale+bias.
