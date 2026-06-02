# saturation-correction

## Formulation
yr = a * yr_v1 + b + c * yr_v1 * (v*yr_v1)^2

The cubic-in-(v*yr_v1) term is a Taylor-style nonlinear understeer correction.
V1 models understeer as `L_eff + K_us * v^2`. Tyres saturate at high a_lat —
this introduces a yr_v1 * a_lat^2 correction.

## State-space
Inputs: V1 yaw rate + measured v. States: none. Memoryless.

## Expected residual character attacked
- Mach-E high-|a_lat| residual that grows from -0.003 (low) to -0.012 (3-5 m/s^2)
- Sign of c>0 means at high |a_lat|, |yr| is amplified

## Verdict expected
Should match or beat affine. Saturation feature is nearly orthogonal to bias so
small additional gain expected — most win comes from b.
