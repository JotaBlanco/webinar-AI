# Research — lateral KS fidelity

> Fill end-to-end before opening `plan.md`. Goal: characterise the residual; do **not** propose fixes.

## Datasets inspected

| Platform | Segment(s) | Duration | Avg |v| (m/s) | Notes |
|---|---|---|---|---|
| FORD_MUSTANG_MACH_E_MK1 | <list> | <s> | <m/s> | |
| FORD_F_150_LIGHTNING_MK1 | <list> | <s> | <m/s> | |

## Baseline residual

| Platform | RMSE ψ̇ (°/s) | RMSE a_y (m/s²) | corr ψ̇ pred-vs-meas | corr a_y pred-vs-meas |
|---|---|---|---|---|
| Mach-E | | | | |
| F-150 | | | | |

## Regime breakdown

Where is the residual worst? Bin by:
- |v| (low / mid / high)
- |δ_road_rad| (straight / mild / hard)
- |a_y_meas| (linear / mid / saturating)

| Bin | Mach-E RMSE ψ̇ | F-150 RMSE ψ̇ | Comment |
|---|---|---|---|

## Failure modes observed

- <pattern 1, with a sketch of the time series and what it suggests physically>
- <pattern 2>
- ...

## Signal-level observations (no fixes yet)

- Is `yaw_rate_resid_rads` biased (non-zero mean)? Sign of bias?
- Does the residual grow with |a_y|? Linear or quadratic?
- Is there a lag/lead between predicted and measured?
- Anything else.

## Open questions for the plan phase

- <question 1>
- ...
