---
name: visualise-segment
description: Render a 3-panel PNG of a single segment — bird's-eye trajectory (x vs y), yaw rate time series, and yaw-rate residual — with the truth overlaid against one or more prediction callables. Use to SEE *where* a model diverges on a specific segment, not just to read aggregate numbers. The callable signature matches the rest of the template — `predict_fn(sim_df, platform) -> DataFrame` with `yaw_rate_pred_rads` (and optional `x_m`, `y_m`).
when-to-invoke: You want a visual diff of one or more model predictions against the truth on a single segment, typically after `score-model` flagged a problematic platform/regime. Not for batch evaluation — that's score-model. Not for loading data — that's load-segments.
inputs: segment_path (Path to sim.csv), predict_fns (dict[str, callable]), out_path (Path), title (str or None), figsize (tuple).
outputs: out_path (Path) — the PNG written to disk.
load-cost: ~110 tokens metadata, ~180 tokens body.
---

# visualise-segment

## What it does

`plot(segment_path, predict_fns, out_path, ...)` renders three stacked subplots into a single PNG:

1. **Bird's-eye trajectory** (x vs y, equal aspect). Truth integrated from `yaw_rate_meas_rads` + `v_mps`. Each prediction overlaid: if its DataFrame carries `x_m` and `y_m`, those are used; otherwise the trajectory is integrated from its `yaw_rate_pred_rads` + `v_mps`. The start point (0, 0) is marked.
2. **Yaw rate vs time** (rad/s). `yaw_rate_meas_rads` as truth, each prediction's `yaw_rate_pred_rads` overlaid.
3. **Yaw rate residual vs time** (`pred - meas`). One line per prediction, with a horizontal zero line.

All three panels share a legend with the prediction names from the `predict_fns` dict keys.

The platform is inferred from the segment path (3rd-from-rightmost directory). The figure title defaults to the last three path components.

## What it does not do

- It does not pick segments for you — pass a `segment_path` in.
- It does not score anything — use `score-model` for KPIs.
- It does not return any data beyond the output Path.

## Usage

```python
from pathlib import Path
from skills.visualise_segment.visualise import plot

def v0(sim_df, platform):
    return sim_df[["yaw_rate_pred_rads"]].copy()

plot(
    segment_path=Path("data/sim-full/FORD_MUSTANG_MACH_E_MK1/<dev>/<route>/1/sim.csv"),
    predict_fns={"v0": v0, "my_model": my_model},
    out_path=Path("out/segment_check.png"),
)
```

## Smoke test

`python3 _smoke.py` — runs `plot` on the first available FORD segment with a V0 passthrough and asserts the PNG was written.

This is a starting point. Modify, extend, or replace as your task demands.
