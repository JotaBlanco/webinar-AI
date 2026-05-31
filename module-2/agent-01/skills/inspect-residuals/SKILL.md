---
name: inspecting-residuals
description: Plot yaw-rate residual (pred - truth) against an arbitrary input feature — steering angle, speed, time, lateral acceleration, or any column you compute and pass in. Scatter coloured by platform, with overlaid per-platform binned mean and ±1σ band. Returns both the matplotlib Figure and a long DataFrame of every (x_value, residual) pair plus a binned summary. Use this after scoring-model surfaces a per-platform bias or unusually wide CTE distribution to discover *which input dimension* the residual depends on.
when-to-invoke: scoring-model showed a non-trivial `yaw_residual_mean`, `yaw_bias_fraction`, or per-platform discrepancy, and you want to see whether the residual is structured against a specific input feature (i.e. is there something the model is missing that a particular signal would explain?).
when-NOT-to-invoke: You want absolute KPI numbers (use scoring-model). You want a per-segment visual of trajectory and yaw vs time (use visualising-segment).
inputs:
  - predict_fn: callable(sim_df, platform) -> DataFrame with `yaw_rate_pred_rads`.
  - x_feature: str, name of a column in sim_df. Default candidates worth trying: `delta_road_rad`, `v_mps`, `t_s`. Any column you can compute on sim_df before calling (e.g. add `sim_df["a_lat"] = sim_df["v_mps"] * sim_df["yaw_rate_meas_rads"]`) is also fair game — pass the augmented df via your `predict_fn` wrapper if needed.
  - segment_paths: list[Path] or None (default — all FORD_*).
  - platform_filter: str or None (limit to one platform).
  - sample_filter_v_mps: float, default 2.0 (same v-filter as scoring-model).
  - bins: int, default 20 (equal-quantile bins for the overlay).
  - max_points_per_platform: int, default 5000 (scatter downsampling cap; DataFrame returned is NOT downsampled).
  - title: str or None.
outputs: dict — residuals (DataFrame), binned (DataFrame), figure (matplotlib Figure), n_segments_used, n_segments_skipped. **Caller saves / shows / closes the figure.**
load-cost: ~170 tokens metadata, ~300 tokens body.
---

# inspecting-residuals

## What it does

For each requested segment:

1. Runs `predict_fn(sim_df, platform)`.
2. Reads `yaw_rate_pred_rads` and `yaw_rate_meas_rads`, filters to `v_mps > sample_filter_v_mps`.
3. Pairs the per-row residual with the per-row value of `x_feature`.

Then, across all segments:

- Builds a long `residuals` DataFrame: `(segment_path, platform, route, x_value, residual)`.
- Bins `x_value` into equal-quantile bins per platform, returns `binned` with mean/std/count.
- Renders a Figure: scatter (coloured by platform, downsampled for readability) + overlaid binned-mean line + ±1σ band per platform, with a horizontal zero line.

You read the figure to ask questions like "is the residual flat across speed, or does it grow at high speed?", "is there a sign-flip around zero steering?", "is the residual structurally different between platforms?".

The skill **does not** tell you which `x_feature` to try, or what the residual structure means. It surfaces the signal; you decide what's going on.

## What it does not do

- Does not write the figure to disk — caller handles output (`fig.savefig(...)`).
- Does not score the model — use scoring-model.
- Does not handle CTE residuals (they're per-distance-bin, not per-row). If you need that, copy this skill to a sibling and replace the per-row pairing with grid-resampled cross-track error.

## Usage

```python
from skills.inspect_residuals.inspect_residuals import inspect_residuals

def v0(sim_df, platform):
    return sim_df[["yaw_rate_pred_rads"]].copy()

# Steering-angle residual structure
out = inspect_residuals(v0, x_feature="delta_road_rad")
out["figure"].savefig("out/resid_vs_steer.png", dpi=130)
print(out["binned"].sort_values(["platform", "x_bin_centre"]).head(20))

# Same predictor, different x-axis — speed
out = inspect_residuals(v0, x_feature="v_mps", platform_filter="FORD_MUSTANG_MACH_E_MK1")
out["figure"].savefig("out/resid_vs_speed_mache.png", dpi=130)
```

If the feature you want isn't in `sim.csv`, compute it inside a thin wrapper of your predictor or extend `loading-segments` to add it.

## Smoke test

`python3 _smoke.py` — runs against ~10 Mach-E segments with V0 passthrough on `x_feature="delta_road_rad"`, asserts the residuals DataFrame is non-empty and the figure is built. Writes the PNG to a temp file so you can eyeball it.

## Extending this skill

If you want to use the same skill for a different residual axis (e.g. CTE per distance bin) or a different overlay (e.g. polynomial fit instead of binned mean), the bin-and-plot code is the bottom half of `inspect_residuals.py` — short enough to fork.
