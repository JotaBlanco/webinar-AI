# lead_compensator — V1 with steering-rate lead term

## Formulation

```
delta_eff(t) = (delta_road(t) - delta_0) + K_d * d(delta_road)/dt
yr_ss(t) = v(t) * g * delta_eff(t) / (L_eff + K_us * v²)
yr(t+dt) = yr(t) + alpha * (yr_ss(t) - yr(t))     # same first-order lag as V1
```

A classical **lead-lag** compensator on the steering input. The added `K_d` term gives V1 a high-pass response to steering rate, intended to recover transient yaw the single-pole lag mis-shapes.

## State-space / integrator

Single state `yr`, forward Euler (zero-order hold). Same as V1.

## Expected residual character attacked

Transient regime (where V1 has ~30-44% of its yaw RMSE²).

## Fitted parameters

Optimised by Nelder-Mead per platform. Notable result: optimiser drove `K_d < 0` on every platform, i.e. wants to **anticipate** (lead) steering, and pushed `tau → 0.01` (essentially no lag). The combination acts as a near-instantaneous gain with a small anti-lead — suggests V1's lag itself is the primary mis-fit, not the absence of a lead term.

## Structurally different from V1?

Differs from V1 by one extra parameter (`K_d`) inserted in the steady-state stage. Marginal numerical gain (pooled yaw 0.01053 vs V1 0.01061; CTE essentially unchanged). Under-parameterised for the non-linear residual.

## Verdict

Ruled out in favour of residual_gb. Useful as a sanity check that the residual can't be cured by adding one more linear knob.
