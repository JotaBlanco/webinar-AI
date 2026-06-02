# v1-steerrate-ff — V1 + steering-rate feedforward

## Formulation

```
yr_v1     = V1(sim_df, platform)
ddelta    = d(delta_road_rad)/dt   (np.gradient)
yr        = yr_v1 · gain_corr + k_dd · ddelta · clip(v, 0, 40) / 30
```

## State-space

State: V1's internal lagged yaw rate (unchanged).
Inputs: V1 inputs + ddelta as an additional input-derivative feature.
Integrator: none additional; V1's first-order lag is the only ODE.

## Parameters (per platform)

Fitted via grid scan over (gain_corr, k_dd).

| platform | gain_corr | k_dd |
|---|---|---|
| Lightning | 1.0000  | −0.040 |
| Mach-E    | 0.9950  | −0.100 |
| IONIQ-5   | 0.9850  | +0.040 |

## Expected residual character

Targets transient-regime residual (V1 RMSE 0.0164 in transient vs 0.0044
straight). The first-order lag is a single-pole approximation of dynamics V1
doesn't model; a steering-derivative term lets the prediction lead/lag the
steering input non-trivially.

## Why this is structurally different from V1

V1 is a function of `(delta, v)` and the previous yaw rate. The feedforward
adds `d(delta)/dt` as a new input dependence — a degree of freedom V1
cannot match by re-tuning its scalar coefficients.

## Result (dev pooled)

**Shelved.** Best fit found only ~0.2–0.7% yaw improvement on each platform
individually, and on Mach-E the CTE was unchanged. The grid scan went to the
edge of the search range on some platforms (k_dd = −0.10 on Mach-E suggests
the steering derivative is *anti-correlated* with the V1 residual, i.e. V1
already over-anticipates — a counter-intuitive sign that hints at integration-
delay artefacts of `np.gradient` rather than real model lag).
