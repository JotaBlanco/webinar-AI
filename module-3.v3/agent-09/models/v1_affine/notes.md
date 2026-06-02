# v1_affine — formulation notes

## Shape

```
y_pred(t) = s_p · y_v1(t) + b_p     where p = platform
```

If `s_p = 1`, `b_p = 0`, this is pass-through to V1 (Lightning, Tesla).

`y_v1(t)` is `code.v1_baseline.predict_v1(sim_df, platform)["yaw_rate_pred_rads"]`.

## State-space

No new state. Pure pointwise transform of V1's output. V1 itself carries the
recurrent state (first-order lag).

## Integrator

None (this is an algebraic map). V1's integrator is unchanged.

## Priors / fit

`s_p` and `b_p` fit by closed-form ordinary least squares on the full
`data/sim/segments/<platform>` pool with `v_mps > 2`. ~430k–2M samples per
platform.

## Expected residual character

Targets the **signed bias** on Mach-E (V1 yaw mean residual -0.00142 rad/s)
and IONIQ-5 (V1 yaw mean residual -0.00075 rad/s) — which integrate into
the CTE drift V1 leaves on these platforms. Does NOT touch transient RMS
error or saturation regimes.

## Structure-vs-V1

`refines-v1`. Same kinematic-single-track core; post-hoc affine cleans up
the residual mean. Will be flagged by preflight as not structurally distinct.
