# Assessment — v1_plus_nonlin

| metric | V1 | v1_plus_nonlin | delta |
|---|---|---|---|
| pooled yaw RMSE | 0.005874 | 0.005600 | **-4.7%** |
| pooled CTE RMSE | 56.81 | 54.37 | **-4.3%** |
| Lightning yaw | 0.00566 | 0.00520 | -8.1% |
| Mach-E yaw | 0.00859 | 0.00762 | -11.3% |
| IONIQ-5 yaw | 0.00766 | 0.00752 | -1.8% |
| Mach-E CTE drift | -21.98 | -5.77 | shrinks by 74% |
| IONIQ-5 CTE drift | -11.57 | -8.62 | shrinks by 25% |

Verdict: **beats V1 on both KPIs**. Mach-E saw the biggest yaw-bias and CTE-drift
collapse — confirming the |delta|*delta signal was a tyre-saturation residual
V1 couldn't represent.
