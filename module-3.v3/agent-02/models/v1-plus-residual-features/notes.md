# v1-plus-residual-features

## Formulation
yr = a*yr_v1 + b + c * yr_v1 * (v*yr_v1)^2 + d * d(delta_road_rad)/dt

This is V1 + per-platform OLS calibration on three input-only features:
- Affine in yr_v1 (compresses bias + scale errors)
- Cubic saturation in yr_v1 * a_lat^2 (tyre nonlinearity)
- Steering-rate ddelta_dt (transient regime, where V1's tau-pole undermodels)

## State-space
Inputs: V1 yaw + v + numerical-derivative of delta. States: none.
The ddelta is computed per-call from the sim_df rows the grader hands us,
so behaviour is identical between local dev and grading.

## Integrator
None for yaw correction; trajectory integration delegated to grader via
clamped-v rule.

## Expected residual character attacked
- Mach-E transient steering: d=-0.022 means a positive steering-rate input
  pulls yaw down. Physical interpretation: the dynamic lag means yr should
  lead delta less aggressively than V1's pole models, in regions where the
  wheel is being turned hard.
- Bias drift via b
- Mild saturation via c

## Fitted coefficients
Lightning: a=0.98393, b=-0.000460, c=+3.97e-04, d=-0.00800
Mach-E:    a=0.97278, b=+0.001698, c=+2.00e-04, d=-0.02207
IONIQ-5:   a=0.99137, b=+0.000639, c=+1.48e-04, d=+0.00451

## Risks
- ddelta is sensitive to dt; np.gradient over a non-uniform t array handles it
  but spike-prone steering can blow up. Clipped to [-2, +2] rad/s.
- d-coefficient signs differ across platforms — physically interpretable
  but possibly overfit to a single dataset slice.
