---
name: route-bias
description: Per-route signed yaw bias and signed CTE drift, ranked by the route's share of the *platform's* pooled error — so you see which routes are the biggest opportunity, not just the noisiest. Includes per-route means of input features (default `v_mps`, `delta_road_rad`, `a_long_mps2`) so you can correlate route bias against an OBSERVABLE feature. Output is diagnostic — route ID is not an inference input, so you cannot apply a route-keyed correction directly; you use this to discover an input feature to add to your model. Schema-aware via `scoring-model`'s `PLATFORM_SCHEMA`.
when-to-invoke: scoring-model's bias-warnings block is lit up on a platform AND fit-model has already squeezed out the platform-level bias, but the residual CTE drift is still uncomfortable. That residual is almost always route-level (cohort evidence) and the per-platform fit can't reach it.
when-NOT-to-invoke: You haven't fitted yet (use scoring-model + fit-model first; only run route-bias on a fitted predict_fn). You want a pretty per-route plot (use inspect-residuals with `platform_filter=` and a wrapper).
inputs: predict_fn, segment_paths (default — all platforms), platform_filter, sample_filter_v_mps, grid_step_m, min_distance_m, feature_means (list of column names to average per route — default `["v_mps", "delta_road_rad", "a_long_mps2"]`), top_n.
outputs: dict — per_route (DataFrame), per_platform_summary, top_routes_by_cte, top_routes_by_yaw_bias, recommendations (list of routes flagged as both biased AND high-share), failed_segments, feature_means.
load-cost: ~200 tokens metadata, ~480 tokens body.
---

# route-bias

## What it does

Runs your `predict_fn` over every requested segment, groups by `(platform, route)`, and computes:

- **Signed yaw bias** per route (`yaw_residual_mean`) — the bias the per-platform fit averaged away.
- **Signed CTE drift** per route (`cte_signed_mean`) — the integrated drift on each route.
- **Share of platform pooled error** (`share_of_platform_yaw_sum_sq` / `..._cte_sum_sq`) — a route's contribution to the platform's total error. **This is the opportunity signal** — a route with moderate bias but 30% share matters more than one with extreme bias but 1% share.
- **Mean of input features** per route (`mean_v_mps`, `mean_delta_road_rad`, `mean_a_long_mps2` by default). Pick the features that match your model's structure — these are what you'll correlate the bias against.

A `recommendations` list flags routes that satisfy BOTH:
- signed bias above the threshold (`|yaw_residual_mean| > 0.0015` rad/s or `|cte_signed_mean| > 5 m`), AND
- share of pooled error above 5%.

The dashboard ranks these first so the agent's eye lands on actionable rows.

## Why this is DIAGNOSTIC, not corrective

The canonical grader calls `predict(sim_df, platform)`. There is no `route` argument. So a `{(platform, route): bias}` lookup cannot be applied at inference — the agent has no way to identify which route the segment belongs to.

The way to *exploit* per-route bias is to find an INPUT FEATURE that correlates with the flagged routes, then add a feature-conditional term to your model:

1. Look at `recommendations` — these are the "big opportunity" routes.
2. Inspect their `feature_means` column. If, say, the flagged Hyundai routes have a much higher `mean_v_mps` than the non-flagged ones, the platform fit is missing a speed-dependent term.
3. Add that term (`yr_corr += g * (v - v_mean) * delta_road`, etc.) and re-fit with `fit-model`.

If you can't find any input feature that explains the route bias, the residual is genuinely route-level (driver style, road geometry not captured in sensors) and your model is at the ceiling.

## Usage

```python
from skills.route_bias.route_bias import route_bias, format_route_bias_summary

result = route_bias(
    my_fitted_predict_fn,
    feature_means=["v_mps", "delta_road_rad", "a_long_mps2"],
)
print(format_route_bias_summary(result))

# Programmatic access — recommendations is the actionable list.
for r in result["recommendations"]:
    print(r["platform"], r["route"], r["feature_means"], r["notes"])
```

## What it does not do

- Does not fit anything. It only measures and ranks. Pair with `fit-model` after you've added a feature-conditional term to your model.
- Does not produce a per-route lookup you can apply at inference. (It cannot — route is not an input.)
- Does not pick which `feature_means` to compute. Pick features that match your model's structure (a model that already has a `v²` term wants `mean(v_mps**2)` as a feature).

## Smoke test

`python3 _smoke.py` — runs V0 passthrough on a small slice across all platforms, asserts per_route is populated for every platform with data, and the recommendation list (if any) has the required keys.

## Extending this skill

- Different threshold: edit `ROUTE_YAW_BIAS_WARN_RAD_S` / `ROUTE_CTE_DRIFT_WARN_M` at the top of `route_bias.py`.
- Different feature: pass a custom `feature_means` list. Anything in the allowlist or raw sim.csv is fair game.
- Correlation column: extend `route_bias()` to compute a per-platform Pearson correlation between `cte_signed_mean` and each feature_mean — the top correlated feature is your next model term candidate.
