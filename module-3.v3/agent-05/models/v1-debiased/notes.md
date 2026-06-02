# v1-debiased

structure: differs-from-v1 (additive residual term, not a coefficient refit)

## Formulation

    yr_hat = predict_v1(sim_df, platform) + b_platform

`b_platform` is a per-platform scalar yaw-bias correction. Fit by scanning a
grid around the V1 mean-residual analytical optimum and choosing the bias
that minimises a normalised (yaw_rmse + cte_rmse) combined metric against V1.

## State-space / inputs

- Inputs: same as V1 (delta_road_rad, v_mps, yaw_rate_pred_rads, t_s).
- State: none beyond V1's internal first-order-lag state.
- Initial conditions: identical to V1.

## Expected residual character attacked

Per-platform signed CTE drift on Mach-E (-22 m) and IONIQ-5 (-12 m). V1's
δ₀ correction handled the bulk but a small persistent yaw bias remained.
CTE is roughly ∫(yaw_pred − yaw_truth)·v dt, so even a 0.001 rad/s bias
integrates to meters of drift over a ~2 km segment.

## Fitted coefficients

    FORD_F_150_LIGHTNING_MK1: -0.00012 rad/s
    FORD_MUSTANG_MACH_E_MK1:  +0.00213 rad/s
    HYUNDAI_IONIQ_5:          +0.00112 rad/s
    TESLA_MODEL_3:             0       (V0 passthrough, no truth)
