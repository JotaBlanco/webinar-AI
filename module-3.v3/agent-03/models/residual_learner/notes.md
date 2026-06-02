# residual_learner — V1 + linear ridge residual

## Formulation

```
yr_pred = yr_v1 + w · phi(t)
```

phi = [1, delta, d_delta/dt, v, yr_v0, yr_v1, v*yr_v0, delta*v, d_delta*v, d(yr_v1)/dt, sign(delta)*delta²].

## State-space / integrator

No state. Closed-form, sample-wise.

## Expected residual character attacked

Same diagnosis as residual_gb (transient regime + delta gain mismatch), but with a strictly **linear** correction head. R² 5/5/2% per platform — confirms residual is non-linear and demands a non-linear head (motivates residual_gb).

## Structurally different from V1?

Yes — added regressors over allowlist features. But only marginally better numerically (1.7% yaw, 4.4% CTE) — under-parameterised for the residual.
