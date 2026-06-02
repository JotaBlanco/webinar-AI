# Assessment — v1_plus_rich (SHIPPED)

| metric | V1 | v1_plus_rich | delta |
|---|---|---|---|
| pooled yaw RMSE | 0.005874 | **0.005552** | **-5.5%** |
| pooled CTE RMSE | 56.81 | **54.56** | **-4.0%** |
| Lightning yaw | 0.00566 | 0.00516 | -8.8% |
| Lightning CTE | 62.19 | 60.96 | -2.0% |
| Mach-E yaw | 0.00859 | 0.00757 | -11.9% |
| Mach-E CTE | 98.68 | 93.33 | -5.4% |
| IONIQ-5 yaw | 0.00766 | 0.00745 | -2.7% |
| IONIQ-5 CTE | 69.53 | 67.18 | -3.4% |
| Tesla | 0 | 0 | passthrough preserved |

Per-regime yaw improvement:
- straight: 0.00442 -> 0.00434 (-1.8%)
- steady: 0.00835 -> 0.00754 (-9.7%)
- transient: 0.01647 -> 0.01565 (-5.0%)

Verdict: **wins on both KPIs across every non-Tesla platform**. Mach-E
benefits most (the worst-fitted platform under V1); IONIQ-5 the least,
hinting its residual is more route-bias-shaped than tyre-shaped (consistent
with the persistent CTE drift -7.2 m even after the correction).
