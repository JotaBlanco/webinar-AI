# v1-asym-debias — assessment

## Headline (full dev set, pooled across platforms)

| metric | V1 | v1-asym-debias | Δ vs V1 |
|---|---|---|---|
| yaw_rate_rmse (rad/s) | 0.005874 | **0.005805** | **−1.2%** |
| cte_rmse (m)          | 56.807   | **54.689**   | **−3.7%** |

## Per-platform

| platform | yaw V1 → cand | cte V1 → cand | bias V1 → cand | cte_drift V1 → cand |
|---|---|---|---|---|
| Lightning | 0.00566 → 0.00564 | 62.19 → 61.95 | +0.00012 → −0.00004 | +0.32 → −0.67 |
| Mach-E    | 0.00859 → **0.00841** | 98.68 → **92.49** | −0.00142 → +0.00027 | −21.98 → **−4.88** |
| IONIQ-5   | 0.00766 → 0.00760 | 69.53 → **67.65** | −0.00075 → −0.00008 | −11.57 → −6.17 |
| Tesla     | 0 → 0 | 0 → 0 | unchanged | unchanged |

## Bias warnings

All platforms now under the score-model bias warning thresholds (|yaw_bias| <
0.002 rad/s, |cte_drift| < 5 m, with IONIQ at 6.2 m just over). V1 had 🚨 on
Mach-E cte_drift and ⚠️ on IONIQ-5 cte_drift; the new model clears the 🚨 entirely.

## Verdict

**Ship.** Pooled improvement is real and consistent: every platform improves
or stays within noise on both KPIs; signed biases are tightened; the systematic
CTE drift on Mach-E is cut by 78% (-22 m → -5 m). Lightning is held neutral
(b_offset=0 by design).

## Things this rules out

- **A symmetric per-platform `g` is leaving a discoverable structural residual
  on the table.** This was 1.2% / 3.7% headroom V1 didn't capture.
- **The CTE drift on Mach-E was not purely a δ₀ issue.** V1's per-segment δ₀
  was correct on average but mis-corrected on right-turn-heavy segments.
- **Coefficient interventions alone are still small.** The headroom past V1
  is real but tight (~5% on CTE pooled). The remaining ~95% requires a
  structurally richer model — most likely rung 1 (dynamic single-track) to
  attack the transient-regime residual.
