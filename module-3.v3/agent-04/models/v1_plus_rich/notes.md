# v1_plus_rich — V1 + 8-feature nonlinear + transient correction

## Formulation
predict = predict_v1(sim_df, platform) + linear_correction(features)

Features (per-platform fitted via ridge regression on V1 residuals against truth):
- 1 (bias)
- |delta|*delta (tyre-saturation)
- v*delta, v^2*delta (extra understeer-rate terms)
- delta^3 (further nonlinearity in delta)
- ddelta/dt (transient sidewall response)
- ddelta/dt * v (speed-modulated transient)
- sign(delta) * delta^2 * v (asymmetric high-load term)

`structure: differs-from-V1` — extends v1_plus_nonlin by attacking the
transient-regime residual (V1 had RMSE 0.0165 in `transient` regime vs 0.0044
straight). ddelta/dt is the contract-safe proxy for "steering rate" that V1's
first-order lag is approximating.

## State-space / integrator
Stateless feed-forward correction added to V1's first-order-lagged yaw rate.
No new integrator; relies on V1 for the dynamic component.

## Expected residual character attacked
1. Tyre understeer saturation (|delta|*delta, delta^3 terms)
2. Transient (steering-rate) response that V1's tau lag only approximates
3. Higher-order speed-coupled understeer
