---
name: comparing-models
description: Diff two predict callables segment-by-segment so you can see *where* one wins and the other loses. Returns a per-segment DataFrame with yaw-rate RMSE, distance-resampled cross-track RMSE, deltas (B minus A), and regime fractions. Also exposes ranked views (`top_regressions`, `top_improvements`), per-platform summaries, and a `format_summary` markdown dashboard. Use to compare a candidate predictor against a baseline (or two candidates) without collapsing to a single scalar.
when-to-invoke: You have two predictors with the same `predict(sim_df, platform) -> DataFrame[yaw_rate_pred_rads]` contract and want to know which segments / platforms / regimes each one owns.
when-NOT-to-invoke: You only want absolute scoring of one model (use scoring-model); you only want to look at a single segment (use visualising-segment).
inputs:
  - predict_fn_a, predict_fn_b: callables. Required column `yaw_rate_pred_rads` (optional `x_m`, `y_m`).
  - segment_paths: optional list of `sim.csv` paths. Default — all `data/sim/segments/FORD_*/**/sim.csv` under cwd.
  - name_a, name_b: column labels (default "A"/"B").
  - grid_step_m, min_distance_m, sample_filter_v_mps: same defaults as scoring-model.
outputs:
  - `compare(...)` -> DataFrame, one row per segment, sorted by segment_path. Columns: segment_path, platform, n_samples, yaw_rate_rmse_{A}, yaw_rate_rmse_{B}, yaw_rate_delta, cte_rmse_{A}, cte_rmse_{B}, cte_delta, frac_straight, frac_steady, frac_transient. **Negative deltas mean B is better.** CTE NaN if segment is shorter than min_distance_m.
  - `top_regressions(df, metric, n)`, `top_improvements(df, metric, n)` -> DataFrames sorted by delta extremes.
  - `per_platform_summary(df, name_a, name_b)` -> per-platform pooled means and win fractions.
  - `format_summary(df, name_a, name_b, top_n)` -> markdown dashboard string.
load-cost: ~150 tokens metadata, ~350 tokens body.
---

# comparing-models

## What it does

For each segment, runs both predictors then computes:

- **yaw-rate RMSE** per side (rad/s) over rows where `v_mps >= sample_filter_v_mps`.
- **CTE RMSE** per side (m), via `_shared/traj_metrics.cte_rmse_segment`. Short segments give NaN.
- **deltas** = B minus A (negative = B better).
- **regime fractions** per segment — `straight | steady | transient`.

Then on top of the raw per-segment table you get:

- `top_regressions(df, "cte_delta", n=10)` — segments where B regressed worst.
- `top_improvements(df, "cte_delta", n=10)` — segments where B improved most.
- `per_platform_summary(df)` — mean A/B/Δ + B-wins-fraction per platform.
- `format_summary(df)` — print a markdown dashboard combining all of the above.

Sign convention is consistent everywhere: **negative delta means B is better than A**.

## What it does not do

- Does not pool across segments into one scalar. Use scoring-model for that.
- Does not score one model alone. Both predict functions are required.
- Does not tell you *which* model is better overall — it gives the numbers, and B-wins-fraction shows the spread.

## Usage

```python
from skills.compare_models.compare import (
    compare, top_regressions, top_improvements, format_summary,
)

def v0(sim_df, platform):
    return sim_df[["yaw_rate_pred_rads"]].copy()

def candidate(sim_df, platform):
    out = sim_df[["yaw_rate_pred_rads"]].copy()
    out["yaw_rate_pred_rads"] *= 1.05
    return out

df = compare(v0, candidate, name_a="v0", name_b="cand")
print(format_summary(df, "v0", "cand"))

regressions = top_regressions(df, "cte_delta", n=20)
```

## Notes for the predictor contract

- Must return a DataFrame aligned with `sim_df.index`, column `yaw_rate_pred_rads`.
- If a predictor raises on a segment, that segment is dropped and a warning is printed.

## Extending this skill

If you want to rank by a custom metric (e.g. `cte_delta` normalised by `cte_rmse_A`), add the column to the result DataFrame in `compare()` and call `top_regressions(df, "your_metric")` — it accepts any column name.
