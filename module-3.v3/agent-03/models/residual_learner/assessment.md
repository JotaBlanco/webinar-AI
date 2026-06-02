# residual_learner — assessment

## Pooled scores

| metric | V1 | residual_learner | delta |
|---|---|---|---|
| yaw RMSE (rad/s) | 0.01061 | 0.01043 | -1.7% |
| CTE RMSE (m)     | 75.65   | 72.35   | -4.4% |

R² per platform: 5% / 5% / 2%. Linear head is **under-parameterised** for the V1 residual — the residual is non-linear (transient × delta × v cross-terms). Motivated the move to GB.

## Verdict

Ruled out in favour of residual_gb. Kept as a baseline structural alternative to demonstrate the residual's non-linearity.
