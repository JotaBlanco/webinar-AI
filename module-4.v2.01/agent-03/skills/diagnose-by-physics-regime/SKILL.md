---
name: diagnose-by-physics-regime
description: Slice a predictor's residual by physics regimes that map to the five prefilled v2.01 models — high-lateral-acceleration (M2 / Fiala territory), heavy-load-transfer (M3 territory), speed-dependent phase lag (M4 territory), longitudinal-coupling (M5 territory), and transient steering (M1 territory). Returns a structured verdict naming which of M1–M5 the residual is most likely to benefit from. Pure-Python, no LLM.
when-to-invoke: After scoring V1 (or any candidate) on dev, when you're deciding which of the five prefilled models to run first. Replaces "stare at score-model output and guess." Also useful after fitting a candidate to see if a residual regime got resolved or moved.
when-NOT-to-invoke: You only have one model option (just score it); the predictor crashes on dev (fix it first); you need per-segment outliers (use score-model's per_segment table).
inputs: predict_fn (callable[sim_df, platform] -> DataFrame[yaw_rate_pred_rads]), segment_paths (list[Path] or None — default = frozen dev split), platform_filter (str or None).
outputs: dict with `regime_rmse` (per-platform, per-regime yaw RMSE + share-of-pooled-error), `model_routing` (ranked list of recommended models with rationale), `format_summary()` (markdown verdict block).
load-cost: ~140 tokens metadata, ~400 tokens body.
---

# diagnose-by-physics-regime

## What it does

For each sim.csv segment, slice rows into five **physics regimes** based on
allowlist columns only — no truth used for the slicing, only the agent's
own `predict_fn` output and the inputs:

| regime | definition (per row) | the model that should help |
|---|---|---|
| `transient_steering` | `|d(δ)/dt| > 0.05 rad/s` | **M1** (linear dynamic ST) |
| `high_lat_accel`     | `|v · ψ̇_pred| > 4 m/s²`  | **M2** (Fiala saturation) |
| `heavy_load_transfer`| platform ∈ {F150} AND `|v · ψ̇_pred| > 2 m/s²` | **M3** (double-track) |
| `brake_or_accel`     | `brake_pressed == 1` OR `|a_long_mps2| > 1.5 m/s²` | **M5** (friction circle) |
| `phase_lag_speed_dep`| split rows by `v` band and compare per-band RMSE — if RMSE rises >50% at extremes | **M4** (relaxation length) |

A row can belong to multiple regimes. RMSE is computed within each regime
independently against the truth column from `PLATFORM_SCHEMA` (same source
as `score-model`).

Then `model_routing` aggregates: which regime carries the largest share of
the pooled residual energy (`RMSE² × n_rows`), and what fraction. Top three
regimes by energy share become the recommended models, with a rationale
string per recommendation.

## Why this exists

The m4.v2 retro found agents spent the first 15 min "looking at score-model
output and guessing what to try next." agent-09 said it directly: "a
harness component that surfaced what fraction of remaining error is bias
I could remove" would have shortened the iteration loop. This skill is
that component, generalised across the five prefilled physics hypotheses.

It is not magic. The mapping `regime → model` is a heuristic grounded in
the physics (`references/dynamics-formulations.md`), not a learned router.
If you disagree with the routing for your data, ignore it — the regime
RMSE table is the diagnostic; the model recommendation is a hint.

## Usage

```python
from skills.diagnose_by_physics_regime.diagnose import diagnose, format_summary
from code.v1_baseline import predict as v1_predict
from _shared.frozen_split import dev_paths

result = diagnose(v1_predict, segment_paths=dev_paths())
print(format_summary(result))

# Or get the structured routing:
for rec in result["model_routing"]:
    print(rec["model"], rec["why"])
```

## Output schema

```
{
  "regime_rmse": {
    "FORD_F_150_LIGHTNING_MK1": {
      "transient_steering":    {"yaw_rmse": 0.012, "n_rows": 4521, "energy_share": 0.18},
      "high_lat_accel":        {...},
      ...
    },
    ...
  },
  "model_routing": [
    {"model": "m3-double-track-load-transfer",
     "energy_share": 0.34,
     "why": "heavy_load_transfer regime carries 34% of pooled residual energy on F150; rung-3 model with lateral load transfer is the prefilled hypothesis."},
    {"model": "m1-linear-dynamic-st", ...},
    ...
  ],
  "pooled_yaw_rmse": 0.00587,
  "n_segments": 415,
}
```
