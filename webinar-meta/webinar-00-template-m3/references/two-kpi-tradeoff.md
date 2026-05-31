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

## Worked example — the per-platform bias-spread diagnostic

Paste this into your dev loop after running `scoring-model`:

```python
from skills.score_model.score import score

result = score(my_model)
for platform, sub in result["per_segment"].groupby("platform"):
    bias_std = sub["yaw_residual_mean"].std()
    print(f"{platform}: std(per-segment yaw bias) = {bias_std:.5f} rad/s")
    if bias_std > 0.002:
        print(f"  → per-segment δ₀ correction is worth trying on this platform")
    else:
        print(f"  → tight already; per-segment correction would add noise")
```

Run this *before* deciding whether to enable per-segment δ₀ for each platform. The threshold (~0.002) is empirical from prior cohorts: above it, the per-segment trick reliably closes the CTE gap; below it, the trick adds noise without signal.

## The two-step diagnostic when global re-fit doesn't close the gap

A common pattern: you re-fit your global parameters per platform, yaw RMSE drops further, but CTE barely moves. This means the bias is **per-segment**, not global. Two steps to confirm and act:

1. **Diagnose**: from `scoring-model`'s output, look at `per_segment["yaw_residual_mean"]`. Compute `std(yaw_residual_mean)` per platform. If `std > ~0.002 rad/s` on a platform, you have per-segment bias that no global parameter can absorb.
2. **Act**: apply gated per-segment δ₀ on that platform (see `anti-patterns.md` § "Legal cousin"). Do NOT apply it on platforms where `std(yaw_residual_mean)` is already tight — the correction adds noise.

This is the single most common "I beat V0 on yaw but CTE is stuck" failure pattern in past cohorts. The bias being chased is per-segment offset, not global.

You should improve on this if you can.

---

## Failure-mode index — check before you commit

| You'll see this if... | What it points to |
|---|---|
| your yaw delta is much bigger than your CTE delta on a platform | residual systematic bias — see "two-step diagnostic" above |
| your CTE got worse while yaw got better | over-fit yaw at the cost of trajectory drift; reduce regularisation or chase the bias source |
| you "smoothed the trajectory" and CTE didn't move | wrong axis — smoothing fights noise, not bias |
| you're reporting only pooled CTE without per-segment breakdown | use `scoring-model`'s `per_segment` table — pooled CTE hides the few segments dominating the residual |
| `per_segment["yaw_residual_mean"]` shows a wide spread but you only re-fit globals | bias is per-segment; the global re-fit can't reach it |
