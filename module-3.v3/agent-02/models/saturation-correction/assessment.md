# Assessment — saturation-correction

## Local dev scores (sim-only/segments/)

| platform | yaw RMSE | CTE RMSE | signed CTE mean |
|---|---|---|---|
| Lightning | 0.01269 | 62.29 | -3.81 |
| Mach-E    | 0.01341 | 91.65 | -1.86 |
| IONIQ-5   | 0.00889 | 67.59 | -4.21 |
| **POOLED** | **0.01053 (-0.7%)** | **72.61 (-4.0%)** | — |

## Verdict: SHELVE (tied with affine — saturation term adds nothing meaningful)
The cubic term coefficient is small and its contribution co-collapses with affine's `a`.
OLS lstsq absorbs almost all of the structure into the linear a term. The
saturation residual is too noisy to lift signal out of linear fit.

## Lesson
Bin-wise diagnostics suggested a strong nonlinear residual, but most of it is
*scale*, not curvature — so a linear gain absorbs most of the win. To get
real value from a saturation correction we'd need to fit the cubic term
separately on a band-pass-filtered residual, or use a dynamic single-track
ODE that has the saturation in the right place mathematically.
