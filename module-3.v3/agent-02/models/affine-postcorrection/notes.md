# affine-postcorrection

## Formulation
yr_pred = a * yr_v1(sim, platform) + b

Per-platform fit by OLS on V1 residual.

## State-space
- Inputs: V1's yaw_rate prediction (a derived feature, not a raw sim input).
- States: none (memoryless on top of V1).
- Initial conditions: V1's initial conditions.

## Integrator
None (point-wise correction).

## Expected residual character attacked
- Mach-E signed CTE drift -22m -> handled by `b` term
- IONIQ-5 signed CTE drift -12m -> handled by `b` term
- Lightning yaw bias (positive) -> handled by `a < 1` (compress)

## Structural novelty vs V1
Treats V1 output as feature; abandons "model is exclusively physics". This is a
*calibration layer*, not a different physics. Tagged structure because the
function class differs.

## Fitted coefficients (OLS on full sim-only dev set, mapped via sim/ truth)
- Lightning: a=0.98695, b=-0.000444
- Mach-E:    a=0.97463, b=+0.001696
- IONIQ-5:   a=0.99207, b=+0.000638
