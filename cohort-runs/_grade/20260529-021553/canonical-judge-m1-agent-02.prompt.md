# Canonical-eval judge prompt template — `grade-cohort-reports`

> Placeholders in `{{double-braces}}`. `prepare_canonical.py` fills them per agent.

---

You are a **canonical-evaluation judge**. Your job is to take ONE agent's reported "favourite" yaw-rate model, reconstruct it, run it against a fixed **held-out validation set**, and report **two primary KPIs** that replace the agent's self-reported headline with comparable, like-for-like, out-of-sample numbers.

We do this because (a) every agent picked their own baseline, their own segment subset, and their own metric definition — so their headline % improvements are not comparable, and (b) every agent trained on the train pool, so scoring on the held-out val pool reveals generalisation, not memorisation. Re-running each model against the same held-out dataset is the only honest cross-agent comparison.

The two primary KPIs:

- **`yaw_rate_rmse`** — pooled-sample yaw-rate RMSE in rad/s, lower is better. Measures instantaneous fidelity.
- **`cte_rmse`** — distance-resampled cross-track-error RMSE in meters, lower is better. Measures cumulative trajectory drift. Per segment, integrate predicted and truth (x, y) from (0,0,0); sample displacement onto a 1m distance grid along the truth path; pool sums-of-squares across segments; take sqrt. Segments with truth-path travel under 20m are excluded.

You report **both** for every agent. They're not redundant — a model that wins yaw-rate but loses CTE is biased (small systematic bias accumulates in trajectory); the model the cohort wants wins both.

The validation segments live under `eval_data_root` (declared in the YAML below). **Agents have never seen this data.** Resolve all `segment_globs` against `eval_data_root`, not against the agent's `data/` symlink.

You have a pre-built helper at `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-meta/skills/grade-cohort-reports/traj_metrics.py` that implements both trajectory integration and the CTE pooling. **Use it.** Do not re-derive the integration scheme.

## The agent

- agent_id: **m1-agent-02**
- agent folder: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-02/final-model`
- report: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-02/final-model/REPORT.md`

## The canonical eval setup (verbatim from the idea's `.canonical.yaml`)

```yaml
idea_id: idea-01-lateral-attribution
description: |
  Canonical evaluation spec for idea-01. Each agent's "favourite" yaw-rate model is
  reconstructed from their report + scripts + outputs, then run against this fixed
  held-out dataset under fixed conditions. The resulting RMSE replaces the agent's
  self-reported headline for cross-agent comparison.

  As of 2026-05-28 the eval set is a held-out validation pool that no agent has seen
  during training. See `split_note` below.

# Absolute path to the validation data root. The segment_globs below are resolved
# relative to this root. Agents are NOT given access to this directory; only the
# grading skill reads from it.
eval_data_root: /Users/javiquix/Desktop/quixdev/F1/KB003/data/val-data

eval_set:
  description: All Ford sim segments under <eval_data_root>/sim/segments/FORD_*/...
  segment_globs:
    - sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv
    - sim/segments/FORD_F_150_LIGHTNING_MK1/**/sim.csv
  sample_filter: "v_mps > 2.0"
  truth_channel: yaw_rate_meas_rads

baseline:
  name: V0 (unmodified KS model)
  source: |
    The sim.csv files ALREADY contain the V0 prediction in the column
    `yaw_rate_pred_rads`. This is the output of `simulate_ks(clamp_v_to_measured=True)`
    with the unmodified model — i.e. V0 by construction.
  computed_once: true   # prepare_canonical.py computes both V0 baselines across all canonical segments and caches them

# Two primary KPIs. Neither dominates; the cohort report shows both side-by-side.
# A model that wins on yaw_rate but loses on cte has a systematic bias accumulating
# in trajectory; a model that wins on both is a real improvement.
metrics:

  - id: yaw_rate_rmse
    name: pooled-sample yaw-rate RMSE
    unit: rad/s
    formula: sqrt(mean((agent_pred - truth)**2)) over all qualifying samples
    sample_filter: "v_mps > 2.0"  # in-motion only
    truth_channel: yaw_rate_meas_rads
    pred_channel_v0: yaw_rate_pred_rads
    improvement_formula: (baseline_rmse - agent_rmse) / baseline_rmse * 100  # positive = better

  - id: cte_rmse
    name: distance-resampled cross-track-error RMSE
    unit: meters
    formula: |
      For each segment, integrate both predicted and truth trajectories from (0,0,0)
      using v_meas. Resample the displacement |pred - truth| onto a uniform distance
      grid (every 1m along the truth path). Pool sums-of-squares and bins across
      segments, then take sqrt(sum_sq / n_bins).
    grid_step_m: 1.0
    min_segment_distance_m: 20.0
    truth_channel: yaw_rate_meas_rads
    pred_channel_v0: yaw_rate_pred_rads
    improvement_formula: (baseline_cte_rmse - agent_cte_rmse) / baseline_cte_rmse * 100  # positive = better
    note: |
      Under the operating contract (clamp_v_to_measured=True), v is the same for
      predicted and truth trajectories, so cumulative distance s is the same in both.
      The Euclidean displacement |pred - truth| at matched s is therefore equivalent
      to |signed cross-track error|. Implementation in grade-cohort-reports/traj_metrics.py.

# Flat per-metric config blocks — readable by the skill's minimal YAML parser
# (which does not recurse into list items). These duplicate the values declared
# in `metrics:` above, but `metrics:` is the human-readable source of truth.

cte_metric:
  grid_step_m: 1.0
  min_segment_distance_m: 20.0
  truth_channel: yaw_rate_meas_rads
  pred_channel_v0: yaw_rate_pred_rads

# Legacy single-metric field — kept for backward compatibility with older grading
# pipelines that read `metric:`. Mirrors the yaw_rate entry above.
metric:
  name: pooled-sample yaw-rate RMSE
  unit: rad/s
  formula: sqrt(mean((agent_pred - truth)**2)) over all qualifying samples
  improvement_formula: (baseline_rmse - agent_rmse) / baseline_rmse * 100

reconstruction_priority:
  - Read fitted coefficients / parameters from agent's out/*.json or out/*.csv if present; combine with the prediction equation described in the REPORT
  - Import and call agent's predict function from tools/*.py
  - Re-run the agent's training script in their folder (slow; only if other options fail)

failure_action: |
  If reconstruction is infeasible — agent didn't save coefficients, code crashes,
  model is described too vaguely to reproduce, or platform-restricted to non-Ford —
  return status="failed" with a one-sentence reason. Do not fabricate numbers.

split_note: |
  This eval set is held out from every agent. Agents see and train against the data
  under webinar-AI/data/ (the train pool); this YAML scores against val-data/, which
  is a separate route-stratified hold-out (split defined in val-data/split.json —
  whole routes held out, ~24% per platform, seed 42). An agent's score here is its
  generalisation, not its in-sample fit.

  Implication: per-segment overfitting tricks (e.g. fitting a bias per segment) will
  no longer score well — the val segments are unseen, so there is nothing per-segment
  to fit at score time unless the agent's predict function recomputes a bias on the
  val segment itself (in which case it is no longer "their model" — it is "their
  procedure," and the score reflects the procedure's generalisation, not memorisation).
```

**Precomputed V0 baseline (cached from the canonical eval set — sanity-check yours against this):**

```json
{
  "yaw_rate": {
    "rmse_rad_per_s": 0.0145625552519141,
    "n_samples_after_filter": 318760,
    "truth_channel": "yaw_rate_meas_rads",
    "sample_filter": "v_mps > 2.0"
  },
  "cte": {
    "rmse_meters": 147.44039440278007,
    "n_segments_used": 122,
    "n_segments_skipped_short": 8,
    "n_segments_skipped_bad": 0,
    "n_distance_bins": 117650,
    "total_distance_m": 117745.51710185508,
    "grid_step_m": 1.0,
    "min_segment_distance_m": 20.0,
    "truth_channel": "yaw_rate_meas_rads",
    "pred_channel": "yaw_rate_pred_rads"
  },
  "n_segments": 130,
  "eval_data_root": "/Users/javiquix/Desktop/quixdev/F1/KB003/data/val-data",
  "globs": [
    "sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv",
    "sim/segments/FORD_F_150_LIGHTNING_MK1/**/sim.csv"
  ],
  "computed_at": "2026-05-29T02:22:20",
  "rmse_rad_per_s": 0.0145625552519141,
  "n_samples_after_filter": 318760,
  "truth_channel": "yaw_rate_meas_rads",
  "sample_filter": "v_mps > 2.0"
}
```

## What you must do

1. **Identify the agent's "favourite" / "final" model.** Read their `REPORT.md`, scripts under `tools/`, and outputs under `out/`. The variant they call best/final/V4/etc. If they report multiple variants, pick the one they label as best in their own words. Quote the line where they declare it.

2. **Reconstruct a callable that produces yaw-rate predictions in rad/s for any sim.csv segment**, using the priority list above:
   1. Read fitted parameters from `out/*.json` or `out/*.csv` and reconstruct the prediction equation from the REPORT's description.
   2. Import and call a predict function from `tools/*.py`.
   3. Re-run the agent's training script in their folder (slow; only if 1/2 fail).

   If none work — agent didn't save coefficients, code crashes, model is described too vaguely to reproduce, or the model is restricted to a non-Ford platform — STOP and report status=`failed` with a one-sentence reason. **Do NOT fabricate numbers.**

3. **Apply to ALL canonical segments.** Resolve the YAML's `segment_globs` against `eval_data_root` (e.g. `<eval_data_root>/sim/segments/FORD_*/...`). For each segment, load `sim.csv`, apply your reconstructed predict to produce a per-row yaw-rate prediction, and store the predictions. **Never substitute the agent's own `data/` symlink** — that points at the train pool, which would re-introduce leakage.

4. **Compute both KPIs.** Stream through each segment once, accumulating both metrics in memory.

   For KPI 1 (`yaw_rate_rmse`):
   - Pool all samples where the YAML's `sample_filter` holds.
   - `agent_yaw_rmse` = RMSE between YOUR reconstructed predictions and the truth channel.
   - `baseline_yaw_rmse_recomputed` = RMSE between sim.csv's existing `yaw_rate_pred_rads` column and the truth channel. Sanity-check: this should match the precomputed `baseline.yaw_rate.rmse_rad_per_s` above to within 1e-6. If it doesn't, flag in `notes`.

   For KPI 2 (`cte_rmse`):
   - Import the helper: `sys.path.insert(0, "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-meta/skills/grade-cohort-reports"); from traj_metrics import cte_rmse_segment`.
   - For each segment, call `cte_rmse_segment(t, v, yr_truth, yr_pred_agent, grid_step_m=1.0, min_distance_m=20.0)` and accumulate `sum_sq` and `n_bins`. Do the same with `yr_pred=yaw_rate_pred_rads` (V0) to recompute the CTE baseline. **Do not** apply the `sample_filter` here — CTE integration needs the full continuous time series per segment.
   - `agent_cte_rmse` = `sqrt(sum_sq_agent / n_bins_agent)` in meters.
   - `baseline_cte_rmse_recomputed` = `sqrt(sum_sq_v0 / n_bins_v0)`. Sanity-check against `baseline.cte.rmse_meters` above.

   Improvement percents:
   - `improvement_pct_yaw = (baseline_yaw_rmse - agent_yaw_rmse) / baseline_yaw_rmse * 100`
   - `improvement_pct_cte = (baseline_cte_rmse - agent_cte_rmse) / baseline_cte_rmse * 100`

5. **Write strict JSON to `/Users/javiquix/Desktop/quixdev/webinar-AI/_grade/20260529-021553/canonical/m1-agent-02.json`.** No prose around it, no markdown fence.

```json
{
  "agent_id": "m1-agent-02",
  "status": "ok",
  "reason": null,
  "reconstruction_method": "json-coeffs | imported-function | re-ran-script | other",
  "reconstruction_summary": "<one sentence — which variant of the agent's model you re-ran and how you got the parameters>",
  "n_segments": <int>,
  "yaw_rate": {
    "n_samples_after_filter": <int>,
    "baseline_rmse": <float — rad/s, copy from baseline.yaw_rate.rmse_rad_per_s>,
    "baseline_rmse_recomputed": <float>,
    "agent_rmse": <float — rad/s>,
    "improvement_pct": <float — positive = better>
  },
  "cte": {
    "n_segments_used": <int — segments with >=20m of truth-path travel>,
    "n_segments_skipped_short": <int>,
    "n_distance_bins": <int>,
    "baseline_rmse_meters": <float, copy from baseline.cte.rmse_meters>,
    "baseline_rmse_recomputed": <float>,
    "agent_rmse_meters": <float>,
    "improvement_pct": <float — positive = better>
  },
  "notes": "<anything noteworthy: 'agent's script seeded RNG, results reproduce exactly', 'agent's coefficients are platform-specific so pooling across Ford platforms loses fidelity', 'wins yaw-rate but loses CTE — bias accumulates', etc.>",
  "_legacy_mirror": {
    "comment": "Top-level fields below mirror the yaw_rate sub-block so older readers and aggregate.py keep working.",
    "baseline_rmse": "<copy of yaw_rate.baseline_rmse>",
    "baseline_rmse_recomputed": "<copy>",
    "agent_rmse": "<copy>",
    "improvement_pct": "<copy>",
    "n_samples_after_filter": "<copy>"
  },
  "baseline_rmse": <copy of yaw_rate.baseline_rmse>,
  "baseline_rmse_recomputed": <copy>,
  "agent_rmse": <copy>,
  "improvement_pct": <copy>,
  "n_samples_after_filter": <copy>
}
```

(The `_legacy_mirror` block is documentation; only the top-level mirror fields after it are read by `aggregate.py`. Keep both — emit the fields, drop the `_legacy_mirror` comment object if you prefer, it is ignored.)

If reconstruction fails, write:

```json
{
  "agent_id": "m1-agent-02",
  "status": "failed",
  "reason": "<one-sentence reason — e.g. 'agent's coefficients not saved and training script requires raw rlog access not available'>",
  "reconstruction_method": "failed",
  "reconstruction_summary": null,
  "n_segments": null,
  "yaw_rate": null,
  "cte": null,
  "baseline_rmse": <float — copy of baseline.yaw_rate.rmse_rad_per_s>,
  "baseline_rmse_recomputed": null,
  "agent_rmse": null,
  "improvement_pct": null,
  "n_samples_after_filter": null,
  "notes": "<context, including what you tried>"
}
```

After writing, return one short sentence: `Canonical eval for m1-agent-02: status=<ok|failed>`. Nothing else.

DO NOT:
- Skip the per-segment loop and sample only a subset for speed.
- Fabricate numbers if reconstruction fails.
- Use any segments outside the canonical val-data set (`eval_data_root`).
- Substitute the train data — agents' `data/` symlinks point at the train pool, NOT the eval pool. Always glob from `eval_data_root`.
- Modify files under `/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-02/final-model/code/` or `/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-02/final-model/data/` (these are symlinks to shared, read-only resources).
- Modify ANY file under `eval_data_root` (this is the canonical val-data pool — read-only by contract).
- Persist bulk per-row predictions to disk. Stream through segments and accumulate RMSE in memory; only the JSON output is needed.

Time budget: ~15 minutes. If your reconstruction approach has been running for &gt;10 minutes with no end in sight, stop, capture what you can, and report `status="failed"` with the reason being "exceeded time budget at <step>".
