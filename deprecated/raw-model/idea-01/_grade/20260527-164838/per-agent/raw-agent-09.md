# raw-agent-09

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-09/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: pooled yaw-rate RMSE over all 520 Ford segments (Mach-E + F-150 Lightning), masked to `v > 2 m/s` (1.36M samples)
- **platform**: Ford segments (Mach-E + F-150 Lightning)
- **baseline_value**: 0.01474 rad/s
- **final_value**: 0.00894 rad/s
- **improvement**: −39.4% RMSE
- **top_contributor**: V4 — understeer `K·v²`

## Honesty flags
- **declared_limitations**: `5`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "Primary metric: pooled yaw-rate RMSE over all 520 Ford segments (Mach-E + F-150 …"; "per-segment `sim.csv` files (which carry `v_mps`, `delta_road_rad`, measured `ya…" |
| contract-acknowledged | binary | True | None | "The KS model already includes `a_long` quantities in the CSV but they're unused …"; "Because the speed-known clamp turns KS into a closed-form lateral predictor, thi…" |
| regime-breakdown-present | binary | False | None | "Primary metric: pooled yaw-rate RMSE over all 520 Ford segments (Mach-E + F-150 …" |
| methodology-consistent | binary | True | None | "Primary metric: pooled yaw-rate RMSE over all 520 Ford segments (Mach-E + F-150 …"; "Shapley value over the four corrections, allocating the total MSE-drop across al…" |
| attribution-coherent | numeric | True | True | "Shapley value over the four corrections, allocating the total MSE-drop across al…"; "Pooled across platforms: V2 + V4 together account for ~85% of the gain, V1 ~3%, …" |
| honest-regression-flagged | binary | None | None | _none_ |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Agent scores against measured yaw_rate_meas_rads from sim.csv, naming the channel as measured and citing the dataset source.
- evidence:
  > Primary metric: pooled yaw-rate RMSE over all 520 Ford segments (Mach-E + F-150 Lightning), masked to `v > 2 m/s` (1.36M samples).
  > per-segment `sim.csv` files (which carry `v_mps`, `delta_road_rad`, measured `yaw_rate_meas_rads`, `a_lat_meas_mps2`, and the baseline KS prediction)

### contract-acknowledged
- result: `True`
- reasoning: Agent explicitly identifies that velocity is clamped to measured (clamp_v_to_measured=True) and yaw rate is predicted by the model.
- evidence:
  > The KS model already includes `a_long` quantities in the CSV but they're unused under `clamp_v_to_measured=True` — there is no lateral-prediction lever there
  > Because the speed-known clamp turns KS into a closed-form lateral predictor, this is exact for ψ̇ and ay

### regime-breakdown-present
- result: `False`
- reasoning: The only breakdown is per-platform (F-150 vs Mach-E); there is no straight/cornering/transient regime breakdown of the metric.
- evidence:
  > Primary metric: pooled yaw-rate RMSE over all 520 Ford segments (Mach-E + F-150 Lightning), masked to `v > 2 m/s` (1.36M samples).

### methodology-consistent
- result: `True`
- reasoning: Single fixed segment set (520 Ford segments, v>2 m/s mask) and one metric (yaw-rate RMSE / MSE-drop) used across all variants in the attribution table.
- evidence:
  > Primary metric: pooled yaw-rate RMSE over all 520 Ford segments (Mach-E + F-150 Lightning), masked to `v > 2 m/s` (1.36M samples).
  > Shapley value over the four corrections, allocating the total MSE-drop across all 24 (n!) ordering permutations

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Shapley scheme guarantees the marginal contributions sum to the total drop by construction; pooled shares (~3+85+9 ≈ 97%) reconcile with total within rounding.
- evidence:
  > Shapley value over the four corrections, allocating the total MSE-drop across all 24 (n!) ordering permutations.
  > Pooled across platforms: V2 + V4 together account for ~85% of the gain, V1 ~3%, V3 ~9%.

### honest-regression-flagged
- result: `None`
- reasoning: Not addressed in report — no variant table row labelled as a regression and no explicit 'no regressions observed' statement.
- evidence: _none_
