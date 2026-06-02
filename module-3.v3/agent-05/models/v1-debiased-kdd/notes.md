# v1-debiased-kdd

structure: differs-from-v1 (adds a steering-derivative correction term)

## Formulation

    yr_hat = predict_v1(sim_df, platform)
           + b_platform
           + k_dd_platform * d(delta_road_rad)/dt

The k_dd term is a feature-engineered residual learner with one input feature: the
finite-difference gradient of measured road-wheel angle.

## State / inputs

- Inputs: V1 + delta_road_rad (already used by V1) + t_s.
- State: none beyond V1's lag state.
- Initial conditions: identical to V1.

## Expected residual character attacked

Transient regime (V1 yaw RMSE 0.0165 vs steady 0.0083 vs straight 0.0044). V1's
first-order lag with τ≈0.07 s is a single-pole approximation of dynamics it
doesn't model. d(delta)/dt is a model-free proxy for the input that lag is
trying to track.

## Fitted coefficients

    FORD_F_150_LIGHTNING_MK1: b=-0.00012, k_dd=-0.010
    FORD_MUSTANG_MACH_E_MK1:  b=+0.00213, k_dd=-0.010
    HYUNDAI_IONIQ_5:          b=+0.00112, k_dd= 0.000  (k_dd added nothing)
