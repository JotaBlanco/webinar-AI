# steer-rate-ff — notes

## Formulation

```
yr_pred = yr_v1(t) + bias + k_ff · v(t) · dδ/dt(t)
```

Per platform: a constant offset `bias` and a single derivative-feedforward
gain `k_ff`. Fit by least-squares on the V1 yaw residual.

In transfer-function terms this turns V1's pure low-pass (single pole, time
constant τ) into a lead-lag with a new zero at `s = -1/(k_ff · v · τ_lag)`-ish.

## State-space

No new states; the V1 lag state remains.

## Integrator

None for the correction term. Standard trajectory Euler integration of yr.

## Priors / fit

`out/fit_steer_rate_ff.py` — least squares on segment rows where v > 2.0
m/s, subsampled at every 4th sample. Two free params per platform.

## Expected residual character (which V1 residual this attacks)

V1's lag time-constant approximates a missing zero in the steering-to-yaw
transfer. The transient regime (|dδ/dt| > 0.05) carries V1's worst yaw
RMSE (0.0165 pooled). Adding a derivative term should attack that region.

## Why this is structurally-different from V1

The first-order lag in V1 is a pole. This adds a zero (in the lead-lag
sense). Pure refitting of V1's `τ` cannot produce a zero.
