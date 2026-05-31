---
name: compare-models
description: Diff two predict callables segment-by-segment so you can see *where* one wins and the other loses. Returns a per-segment DataFrame with yaw-rate RMSE, distance-resampled cross-track RMSE, deltas (B minus A), and regime fractions (straight/steady/transient). Use this to compare a candidate predictor against a baseline (or two candidates against each other) without collapsing everything to a single scalar.
when-to-invoke: You have two predictors with the same `predict(sim_df, platform) -> DataFrame[yaw_rate_pred_rads]` contract and you want to know on which segments / regimes one beats the other. Not for absolute scoring of one model — use `score-model` for that.
inputs:
  - predict_fn_a: callable(sim_df, platform) -> DataFrame with `yaw_rate_pred_rads` (and optionally `x_m`, `y_m`).
  - predict_fn_b: same contract.
  - segment_paths: optional list of `sim.csv` paths. Default: all `data/sim/segments/FORD_*/**/sim.csv` under the working dir.
  - name_a, name_b: labels that appear in the result columns (default "A"/"B").
  - grid_step_m, min_distance_m: passed through to the shared CTE helper.
  - sample_filter_v_mps: rows with v_mps below this are excluded from the yaw-rate RMSE (default 2.0). CTE always uses the full series.
outputs:
  - pandas.DataFrame, one row per segment, sorted by `segment_path`. Columns: `segment_path`, `platform`, `n_samples`, `yaw_rate_rmse_{name_a}`, `yaw_rate_rmse_{name_b}`, `yaw_rate_delta`, `cte_rmse_{name_a}`, `cte_rmse_{name_b}`, `cte_delta`, `frac_straight`, `frac_steady`, `frac_transient`. CTE columns are NaN for segments shorter than `min_distance_m`. Negative deltas mean B is better.
load-cost: ~120 tokens metadata, ~250 tokens body, plus pandas/numpy at runtime.
---

# compare-models

## What it does

For each segment, runs both predictors, then computes:

- **yaw-rate RMSE** per side (rad/s) over rows where `v_mps >= sample_filter_v_mps`.
- **distance-resampled cross-track RMSE** per side (m), via the shared `_shared/traj_metrics.cte_rmse_segment` helper. Segments shorter than `min_distance_m` get `NaN` here.
- **deltas** = B minus A (negative = B better).
- **regime fractions** classifying each row as:
  - `straight`: `|delta_road_rad| < 0.01`
  - `steady`: not straight AND `|d(delta_road_rad)/dt| < 0.05 rad/s`
  - `transient`: otherwise

You eyeball the result to ask questions like "does B improve transient segments at the cost of steady ones?" or "is the CTE delta correlated with platform?". The skill does not answer those questions for you.

## What it does not do

- Does not pool across segments. Use `score-model` if you want a single scalar.
- Does not score one model alone. Both `predict_fn_a` and `predict_fn_b` are required.
- Does not mutate the input `sim_df`. Each predictor sees a fresh slice.
- Does not tell you which model is "better" — it gives you the numbers.

## Usage

```python
from skills.compare_models.compare import compare

def fn_baseline(sim_df, platform):
    # V0 — kinematic bicycle prediction is already in the CSV.
    return sim_df[["yaw_rate_pred_rads"]].copy()

def fn_candidate(sim_df, platform):
    out = sim_df[["yaw_rate_pred_rads"]].copy()
    out["yaw_rate_pred_rads"] *= 1.05  # toy candidate
    return out

df = compare(fn_baseline, fn_candidate, name_a="v0", name_b="cand")
df.sort_values("yaw_rate_delta").head(10)   # segments where candidate wins most
```

## Notes for the predictor contract

- Must return a DataFrame aligned with `sim_df.index`. A `yaw_rate_pred_rads` column is required. `x_m` and `y_m` columns are optional — if absent, CTE integrates the trajectory from the predicted yaw rate and the measured `v_mps`.
- If a predictor raises on a segment, that segment is dropped from the output and a one-line warning is printed. Use this to debug your predictor.

This is a starting point. Modify, extend, or replace as your task demands.
