# v1-debiased-kdd — assessment

**Verdict**: equivalent to v1-debiased to 5 decimals. k_dd buys essentially nothing.
Not shipping over v1-debiased.

| platform | yaw RMSE | CTE RMSE |
|---|---|---|
| FORD_F_150_LIGHTNING_MK1 | 0.00565 | 62.18 |
| FORD_MUSTANG_MACH_E_MK1 | 0.00850 | 91.27 |
| HYUNDAI_IONIQ_5 | 0.00764 | 67.03 |
| **pooled** | **0.00584** | **54.19** |

## Why k_dd didn't help

The grid search over k_dd at the optimum bias scanned [-0.2 .. +0.2] and the best per platform
was within 0.0001 of the bias-only model. Interpretation: V1's first-order lag already models
the transient response well enough that a linear-in-d(δ)/dt correction has no signal left to
extract. To attack the transient regime structurally, you'd need a model that actually has
slip-angle dynamics — i.e. a rung-1 dynamic single-track ODE — not a residual linear term.

The k_dd direction (negative) is consistent with "V1 over-shoots the transient" — but the gain
that minimises RMSE is essentially zero, so the lag is already doing the right thing.
