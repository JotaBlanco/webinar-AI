---
name: scoring-model
description: Score any predict callable against segment sim.csv files and return a rich diagnostic bundle — pooled yaw-rate RMSE (rad/s) and pooled distance-resampled CTE RMSE (m); a per-segment table; per-platform residual statistics (signed bias, std, bias fraction, signed CTE drift); per-route pooled errors; per-regime yaw stats; worst-N outlier tables; full distribution stats; signed-bias warnings. Schema-aware — resolves the ground-truth column per platform via `PLATFORM_SCHEMA`, so platforms whose sim.csv uses a non-default column name (e.g. Tesla's `psi_dot_rads`) score instead of being silently skipped. Use as the inner-loop oracle while iterating on a model. The callable signature is fixed — `predict_fn(sim_df, platform) -> DataFrame` with a `yaw_rate_pred_rads` column.
when-to-invoke: You have a model (any Python callable matching the signature) and want a complete view of how it performs — not just headline KPIs but also which segments dominate the error, whether residuals are biased or noisy, and how performance varies by platform / route / regime.
when-NOT-to-invoke: You only need to load raw segment data (use loading-segments); you want to compare two models head-to-head (use compare-models, which is built for diffs); you want to optimise coefficients against an objective (use fitting-model).
inputs: predict_fn (callable), segment_paths (list[Path] or None), platform_filter (str or None), grid_step_m (float), min_distance_m (float), sample_filter_v_mps (float), top_n (int — default 10).
outputs: dict — keys yaw_rate_rmse, cte_rmse, n_segments, n_samples, failed_segments, failed_by_platform, platforms_seen, per_platform, per_regime, per_segment (DataFrame), per_route (DataFrame), worst_segments_by_cte, worst_segments_by_yaw, yaw_rmse_distribution, cte_rmse_distribution, bias_warnings.
load-cost: ~200 tokens metadata, ~520 tokens body.
---

# scoring-model

## What it does

`score(predict_fn, ...)` runs your `predict_fn` over every requested segment in one pass, then returns one structured result with every diagnostic view you would normally compute by hand:

- **Pooled headline KPIs** — `yaw_rate_rmse` (sample-pooled, v-filtered) and `cte_rmse` (distance-bin-pooled). Definitions live in `_shared/traj_metrics.py`.
- **Signed-bias check** (`bias_warnings`) — a list of `{platform, metric, value, threshold, severity}` for every platform whose signed yaw bias or signed CTE drift is large enough to systematically dominate the integrated error. Rendered at the top of `format_summary()` with 🚨/⚠️ markers. CTE is a double-integral of yaw error — a non-zero signed bias is what kills CTE-RMSE, not the per-sample noise floor. **Look at this before you ship.** Thresholds are module-level constants (`YAW_BIAS_WARN_RAD_S`, `CTE_DRIFT_WARN_M`) — edit them if your tolerance is different.
- **Per-segment table** (`per_segment` — pandas DataFrame): one row per scored segment with `yaw_rate_rmse`, `yaw_residual_mean` (signed), `yaw_residual_std`, `cte_rmse`, `cte_signed_mean` (positive = predicted trajectory to the left of truth), `cte_abs_mean`, `end_drift_m`, `distance_m`, route, idx. This is the workhorse — sort/filter it however you like.
- **Per-platform stats** (`per_platform`): pooled yaw RMSE, **signed yaw bias**, yaw std, **bias fraction** `mean²/(mean²+var)` ∈ [0,1] (high = systematic offset, low = noise), pooled CTE RMSE, **signed CTE drift**, the `truth_col` actually used for that platform, plus any `schema_note`.
- **Per-route pooled** (`per_route` — DataFrame, default-sorted by `cte_rmse` desc): one row per route across its segments.
- **Per-regime** (`per_regime`, yaw only): `straight | steady | transient` rmse + signed mean.
- **Worst-N outliers**: `worst_segments_by_cte` and `worst_segments_by_yaw` as ranked dict lists (default top 10).
- **Distributions**: `yaw_rmse_distribution` and `cte_rmse_distribution` — min / p25 / median / mean / p75 / max / std across segments.
- **Failure breakdown**: `failed_segments` plus `failed_by_platform` so a silent drop is visible.

Regime row labels (yaw only — CTE is a trajectory integral, slicing it by row-regime is not meaningful):
- `straight`: `|delta_road_rad| < 0.01`
- `steady`: not straight AND `|d(delta_road_rad)/dt| < 0.05 rad/s`
- `transient`: otherwise

If `predict_fn` raises, returns the wrong shape, or is missing the required column on a given segment, that segment is skipped and counted under `failed_segments` and `failed_by_platform`.

## Per-platform schema (`PLATFORM_SCHEMA`)

Different platforms in the sim dataset use different column names for ground truth and for the V0 baseline. `PLATFORM_SCHEMA` at the top of `score.py` maps each platform to its `truth_col` and `baseline_col`. Score-model resolves the truth column per platform and, when a platform's baseline is named something other than `yaw_rate_pred_rads` (e.g. Tesla's `psi_dot_rads`), aliases it into `sim_df_agent["yaw_rate_pred_rads"]` so your `predict()` signature stays uniform across platforms.

Concrete consequence: the cohort bug where Tesla was silently skipped because `yaw_rate_meas_rads` doesn't exist on Tesla's sim.csv is gone — Tesla now resolves to `psi_dot_rads` and scores. To add a new platform or fix a column rename upstream, edit the dict at the top of `score.py`.

The Tesla caveat (`schema_note`) is propagated through `per_platform[*]["schema_note"]` and printed under the per-platform table by `format_summary()`.

## A pre-built dashboard print

`format_summary(result)` returns a markdown dashboard you can `print()` — overall KPIs, per-platform table, per-regime, distributions, top-5 worst segments by each metric, top-5 routes by CTE. Useful when you don't want to navigate the dict by hand.

## Usage

```python
from skills.score_model.score import score, format_summary

def my_model(sim_df, platform):
    out = sim_df[["yaw_rate_pred_rads"]].copy()  # V0 passthrough
    return out

result = score(my_model)
print(format_summary(result))

# Or drive your own analysis off the per-segment DataFrame:
worst_routes = result["per_route"].head(5)
mache_bias  = result["per_platform"]["FORD_MUSTANG_MACH_E_MK1"]["yaw_residual_mean"]
```

## What it does not do

- It does not load raw data for you — pass paths in (or let it default to all `data/sim/segments/*/**/sim.csv`, which is *all* platforms; the older `FORD_*` glob silently excluded Hyundai and Tesla and is gone).
- It does not pick a methodology — knobs (`grid_step_m`, `min_distance_m`, `sample_filter_v_mps`, `top_n`) are explicit arguments.
- It does not optimise anything. It returns numbers; you decide what to fit. The companion skill for fitting is `fitting-model`.

## Smoke test

`python3 _smoke.py` — V0 passthrough on ~5 segments, asserts every key is present, prints the formatted summary.

## Extending this skill

If the signal you need isn't in the per-segment table, add a column to it in `score.py`. The whole point of this skill being small is so you can edit it in one sitting. Useful extensions other agents have wanted: per-segment yaw_rate_meas variance (to spot quiet vs busy segments), residual autocorrelation, per-platform per-route cross-tabulation.

## m4 addendum — CV and the test-split gate

m4 adds two disciplines on top of the m3.v2 scorer. Both are wrappers around
`score()`; the underlying scorer is unchanged.

### k-fold route-grouped CV on dev (`score_cv`)

```python
from skills.score_model.cv import score_cv
result = score_cv(predict_fn, k=5)
# result["pooled"] now has mean ± std per metric.
```

`score_cv` partitions the dev split into k=5 route-grouped folds (no route ID
crosses folds — see `make-train-dev-split` for the leakage validator),
scores the candidate on each, and returns `mean ± std`. The σ is what tells
the agent whether a +0.3% improvement vs parent is signal or noise.

This is the discipline that catches the agent-07 cohort failure mode
(`references/m4-cohort-findings.md` §6 — asymmetric-bias subset fit flipped
Lightning's sign on 80-segment splits). Use `score_cv` from `iterate`
automatically; use `score()` directly only for quick mid-iteration sanity
checks.

### Test split refusal

`score()` and `score_cv()` refuse to read from `data/sim-only/test/` (or
`data/sim/test/`) unless invoked with `final=True`. The test split is the
agent's honest stopping signal — it is *only* read once, by
`pre-flight-final-model --final`. Any attempt to score on test during the
inner loop raises a `TestSplitDeniedError`.

Why: CMU 2026 showed that with a verifier in the loop, the verification gap
*widens* with sample count. Every iteration risks overfitting the thing the
agent can score against. The frozen test split is the cheapest insurance
against that — see `references/closing-the-loop.md` § "CV and the dev/test
split".
