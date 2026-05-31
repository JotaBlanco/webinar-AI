---
name: score-model
description: Score any predict callable against a list of segment sim.csv files. Returns pooled yaw-rate RMSE (rad/s) and pooled distance-resampled CTE RMSE (m), plus per-platform and per-regime (straight / steady / transient) breakdowns. The callable signature is fixed — `predict_fn(sim_df, platform) -> DataFrame` with a `yaw_rate_pred_rads` column (and optional `x_m`, `y_m`).
when-to-invoke: You have a model (any Python callable matching the signature) and want a single KPI dict to compare against the baseline or to slice by platform / driving regime. Not for loading raw data — use load-segments for that.
inputs: predict_fn (callable), segment_paths (list[Path] or None), platform_filter (str or None), grid_step_m (float), min_distance_m (float), sample_filter_v_mps (float).
outputs: dict with keys yaw_rate_rmse, cte_rmse, n_segments, n_samples, per_platform, per_regime, failed_segments.
load-cost: ~120 tokens metadata, ~250 tokens body.
---

# score-model

## What it does

`score(predict_fn, ...)` runs your `predict_fn` over every requested segment, pools the two KPIs across all qualifying samples / distance-bins, and also reports per-platform and per-regime slices.

- **yaw-rate RMSE**: sample-pooled across rows where `v_mps > sample_filter_v_mps`.
- **CTE RMSE**: distance-bin-pooled across segments whose travelled distance exceeds `min_distance_m`. The CTE math lives in `_shared/traj_metrics.py` — this skill imports it so the metric is identical everywhere.

Regime labels (per row):
- `straight`: `|delta_road_rad| < 0.01`
- `steady`: not straight AND `|d(delta_road_rad)/dt| < 0.05 rad/s`
- `transient`: otherwise

Per-regime only reports yaw-rate RMSE — CTE is a trajectory integral, slicing it by row-regime is not meaningful.

If `predict_fn` raises, returns the wrong shape, or is missing the required column on a given segment, that segment is skipped and counted under `failed_segments`.

## What it does not do

- It does not load your data for you — pass paths in (or let it default to all `data/sim/segments/FORD_*/**/sim.csv`).
- It does not pick a methodology — knobs (`grid_step_m`, `min_distance_m`, `sample_filter_v_mps`) are explicit arguments with sensible defaults.
- It does not tell you whether your model is good. It returns numbers.

## Usage

```python
from skills.score_model.score import score
import pandas as pd

def my_model(sim_df, platform):
    out = pd.DataFrame(index=sim_df.index)
    out["yaw_rate_pred_rads"] = sim_df["yaw_rate_pred_rads"]  # V0 passthrough
    return out

result = score(my_model, platform_filter="FORD_MUSTANG_MACH_E_MK1")
print(result["yaw_rate_rmse"], result["cte_rmse"])
print(result["per_regime"])
```

## Smoke test

`python3 _smoke.py` — uses a trivial V0 passthrough on ~5 segments and asserts the dict shape.

This is a starting point. Modify, extend, or replace as your task demands.
