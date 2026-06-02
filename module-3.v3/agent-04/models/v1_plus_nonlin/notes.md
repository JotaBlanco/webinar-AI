# v1_plus_nonlin — V1 + small nonlinear correction

## Formulation
predict = predict_v1(sim_df, platform) + linear_correction(features)

Correction features (per-platform fitted):
- 1 (bias)
- |delta|*delta (signed quadratic in delta — tyre saturation)
- v*delta
- v^2*delta

`structure: differs-from-V1` — attacks V1's residual structure (|delta|*delta
correlation observed at +0.25 to +0.35) which V1's linear understeer cannot
represent.

## State-space / integrator
Stateless feed-forward correction added to V1's first-order-lagged yaw rate.

## Expected residual character attacked
- V1 understeer is *linear* (yr_ss ~ v*delta / (L + Kus*v^2*delta)); the
  residual analysis showed |delta|*delta correlated +0.25/+0.35 on Lightning
  and Mach-E, which is the tyre-saturation signature. This correction maps to
  rung-2-ish behaviour without an ODE.
