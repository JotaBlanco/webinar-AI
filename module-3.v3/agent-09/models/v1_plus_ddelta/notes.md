# v1_plus_ddelta — notes

## Shape

```
y = y_v1 + k_ff · d(δ_road)/dt · gate(|δ_road|)
gate = clip((|δ| - 0.005) / 0.005, 0, 1)
```

Adds a feed-forward term derived from the steering-angle derivative, gated
by a soft envelope so it doesn't fire on near-straight driving.

## State

V1's state. The derivative is computed pointwise (central difference via
np.gradient).

## Priors / fit

k_ff fit by closed-form least squares against (truth - V1) on rows where
v>2, |δ|>0.005, |ḋ|>0.05 (transient mask).

Fitted values:
- Lightning: k_ff = -0.0127
- Mach-E:    k_ff = -0.0095
- IONIQ-5:   k_ff = +0.0004 (negligible)

## Expected residual character

Targets V1's transient-regime yaw RMSE (0.0165 pooled). The first-order lag
in V1 is a single-pole approximation; residual ḋ-correlation is the natural
next term.

## Structure-vs-V1

`differs-from-v1`: V1 has no derivative-of-input term. The shape adds a new
input channel and a new gain.
