---
name: inspecting-residuals
description: Plot yaw-rate residual (pred - truth) against one or two input features. 1-D mode → scatter coloured by platform + per-platform binned mean ± σ band. 2-D mode → per-platform heatmap of mean residual over (x, y) cells, with a diverging colour scale so signed bias jumps out. Schema-aware — resolves each platform's truth column via `scoring-model`'s `PLATFORM_SCHEMA` so Tesla and any non-default-schema platform participate. Use after scoring-model surfaces a per-platform bias or unusually wide CTE distribution, to discover *which input dimension* the residual depends on.
when-to-invoke: scoring-model showed a non-trivial `yaw_residual_mean`, `yaw_bias_fraction`, or per-platform discrepancy. 1-D first; 2-D when the residual visibly depends on two axes at once (e.g. understeer is steering × v² so neither axis alone explains it).
when-NOT-to-invoke: You want absolute KPI numbers (use scoring-model). You want a per-segment visual of trajectory and yaw vs time (use visualising-segment).
inputs (1-D):
  - predict_fn: callable(sim_df, platform) -> DataFrame with `yaw_rate_pred_rads`.
  - x_feature: str — column name. Resolved from the agent-view sim_df first; falls back to raw sim.csv. Default candidates: `delta_road_rad`, `v_mps`, `t_s`.
  - segment_paths: list[Path] or None (default — ALL platforms under `data/sim/segments/*/**/sim.csv`).
  - platform_filter, sample_filter_v_mps, bins, max_points_per_platform, title: as before.
inputs (2-D):
  - As 1-D, plus `y_feature` (second column name), `bins=(nx, ny)`, `min_cell_n` (cells below this count are NaN-masked in the plot), `cmap` (default `RdBu_r`), `symmetric_color_scale` (default True so zero is white).
outputs (1-D): dict — residuals (DataFrame), binned (DataFrame), figure, n_segments_used, n_segments_skipped, skipped_by_platform.
outputs (2-D): dict — residuals (DataFrame with x_value AND y_value cols), heatmaps ({platform: {x_edges, y_edges, mean, count}}), figure, n_segments_used, n_segments_skipped, skipped_by_platform. **Caller saves / shows / closes the figure.**
load-cost: ~200 tokens metadata, ~480 tokens body.
---

# inspecting-residuals

## Two modes

### 1-D — `inspect_residuals(predict_fn, x_feature, ...)`

For each requested segment:

1. Strips sim_df to the operating-contract allowlist (matches scoring-model).
2. Resolves the per-platform truth column via `PLATFORM_SCHEMA` and aliases the V0 baseline to `yaw_rate_pred_rads` when needed (Tesla's `psi_dot_rads`).
3. Runs `predict_fn(sim_df_agent, platform)`, computes per-row `residual = pred - truth` after the `v > sample_filter_v_mps` mask.
4. Pairs the residual with the per-row value of `x_feature`.

Then across all segments:

- Long `residuals` DataFrame: `(segment_path, platform, route, x_value, residual)`.
- Per-platform equal-quantile bins → `binned` with mean/std/count.
- Figure: scatter coloured by platform (downsampled for readability) + binned-mean line + ±1σ band + zero line.

You read it to ask things like: "is the residual flat across speed, or does it grow at high v?", "is there a sign-flip around zero steering?", "do platforms have structurally different residual shapes?". The skill surfaces signal — it does not interpret.

### 2-D — `inspect_residuals_2d(predict_fn, x_feature, y_feature, ...)`

Same residual computation, then bin per-platform onto an (nx × ny) equal-quantile grid and plot one heatmap panel per platform with a diverging colour map (`RdBu_r`) on a symmetric scale so zero is white.

**This is what to use when 1-D plots can't tell understeer-shape from hysteresis-shape**, because both are jointly conditional on speed AND steering. v2 cohort agents asked for this explicitly — a 1-D residual-vs-steer plot folds the speed dependence into noise, and v.v.

Output `heatmaps` is a dict keyed by platform, each value `{x_edges, y_edges, mean, count}` — useful when you want to extract the bias structure programmatically (e.g. fit a regression to the heatmap cells).

## What it does not do

- Does not write figures to disk — caller handles `fig.savefig(...)`.
- Does not score the model — use scoring-model.
- Does not handle CTE residuals (they're per-distance-bin, not per-row). Fork this skill to a sibling if you need that.
- Does not pick `x_feature` / `y_feature` for you. Pick them based on which signal scoring-model says is biased.

## Usage

```python
from skills.inspect_residuals.inspect_residuals import (
    inspect_residuals, inspect_residuals_2d,
)

def v0(sim_df, platform):
    return sim_df[["yaw_rate_pred_rads"]].copy()

# 1-D: speed dependence
out = inspect_residuals(v0, x_feature="v_mps")
out["figure"].savefig("out/resid_vs_speed.png", dpi=130)
print(out["binned"].head(20))

# 2-D: understeer-shape diagnostic — residual over (delta, v).
# A pure understeer bias shows as a band whose magnitude grows with v² at any
# fixed sign of delta; a hysteresis bias shows as a sign-flip around delta=0.
out = inspect_residuals_2d(
    v0, x_feature="delta_road_rad", y_feature="v_mps",
    bins=(20, 20), min_cell_n=10,
)
out["figure"].savefig("out/resid_heatmap_delta_v.png", dpi=130)
print(list(out["heatmaps"].keys()))
```

If the feature you want isn't in `sim.csv`, compute it inside a thin wrapper of your predictor or extend `loading-segments` to add it.

## Smoke test

`python3 _smoke.py` — exercises both modes across ALL four platforms with V0 passthrough on `(delta_road_rad, v_mps)`. Asserts Tesla is not silently dropped (it was in earlier versions because the FORD_* glob default and the hardcoded `yaw_rate_meas_rads` truth column excluded it). Writes both PNGs to temp.

## Extending this skill

The bin-and-plot internals (`_bin_per_platform`, `_bin_2d_per_platform`, `_make_figure_1d`, `_make_figure_2d`) are short on purpose. Swap the diverging colormap, log-scale the residual axis, replace mean with median — all small edits.
