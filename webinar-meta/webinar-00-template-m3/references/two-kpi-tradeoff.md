---
name: two-kpi-tradeoff
description: How yaw-rate RMSE and CTE RMSE relate. What it means when a model wins one and loses the other. Useful for diagnosing whether your model has noise, bias, or both.
when-to-load: After you have a model that beats V0 on at least one KPI. Helps interpret what your numbers are telling you.
load-cost: ~400 words.
---

# The two-KPI tradeoff

You're graded on two KPIs: yaw-rate RMSE (rad/s) and distance-resampled CTE RMSE (m). They are not redundant. A model that wins one and loses the other is telling you something specific.

## What each KPI captures

- **Yaw-rate RMSE** is instantaneous fidelity. It penalises noise and bias in predicted yaw rate at every sample.
- **CTE RMSE** is cumulative drift. Predicted and truth trajectories are integrated from (0, 0, 0); the path-displacement is sampled every metre. A model with a tiny *persistent* yaw-rate bias — invisible in RMSE because it averages with noise — accumulates heading error over the segment, compounding into metres of position drift.

The asymmetry: **a small bias hurts CTE far more than it hurts yaw RMSE.** A 0.001 rad/s constant bias might look like a 5% improvement on yaw RMSE while drifting dozens of metres at the segment's end.

## Reading the four patterns

| Pattern | Diagnosis |
|---|---|
| Wins both | Real improvement. Ship it. |
| Wins yaw, loses CTE | Yaw is noisy but unbiased; a small *systematic* bias survives the RMSE pool and accumulates in the trajectory. Look for sign biases (steering offset, K_us slightly wrong) and fix them. |
| Loses yaw, wins CTE | Yaw has high-frequency oscillations that average over distance; or the model predicts conservatively (smaller yaw than truth) and the integration luckily produces less drift than V0. Worth digging into; not always good. |
| Loses both | Real regression. Don't ship. |

## Practical implication

If your yaw improvement is much larger than your CTE improvement (e.g. yaw -45% but CTE only -25%), you have residual systematic bias. The bias is small enough that it averages with noise in the RMSE pool but coherent enough to drift the trajectory. Common sources:

- A platform-mismatched `K_us` (your model was tuned mostly on one platform).
- A `δ₀` (steering offset) you didn't fit or fitted wrong.
- A steering scale `g` slightly off.
- Cumulative effects of a few outlier samples on long segments.

The fix is rarely "smooth the trajectory" or "reduce noise" — those tackle the wrong axis. The fix is to find the bias source in the *time-domain* yaw-rate plot and remove it physically.

You should improve on this if you can.
