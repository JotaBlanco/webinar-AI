# raw-agent-01

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-01/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: pooled yaw-rate RMSE (rad/s, reported in deg/s), on Tesla Model 3 segments, activity-masked (v ≥ 5 m/s **and** |ψ̇_truth| ≥ 2 deg/s; n ≈ 85 300 samples across 120 segments)
- **platform**: Tesla Model 3
- **baseline_value**: 2.763 deg/s
- **final_value**: 2.547 deg/s
- **improvement**: –0.215 deg/s, **–7.8 %**
- **top_contributor**: C1 (effective steer-ratio α)

## Honesty flags
- **declared_limitations**: `6`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | False | None | "I had to fabricate one from the rear wheel-speed differential `(v_RL – v_RR) / t…" |
| contract-acknowledged | binary | True | None | "The model under attack is the existing CommonRoad KS predictor: `ψ̇ = v · tan(δ)…" |
| regime-breakdown-present | binary | False | None | "Improvement is concentrated in the 5–20 m/s band (≈ 12–20 % RMSE reduction); at …" |
| methodology-consistent | binary | True | None | "activity-masked (v ≥ 5 m/s **and** |ψ̇_truth| ≥ 2 deg/s; n ≈ 85 300 samples acro…" |
| attribution-coherent | numeric | True | True | "| **C1 (effective steer-ratio α)** | **+0.155** | **71.9 %** |"; "Cumulative (waterfall) accounting agrees to within 1 percentage-point — most of …" |
| honest-regression-flagged | binary | None | None | _none_ |

## Per-item reasoning
### truth-channel-correct
- result: `False`
- reasoning: Agent explicitly fabricated a proxy from wheel-speed differential rather than scoring against a measured yaw-rate channel.
- evidence:
  > I had to fabricate one from the rear wheel-speed differential `(v_RL – v_RR) / track_rear` with `track_rear = 1.580 m` (public Tesla M3 spec).

### contract-acknowledged
- result: `True`
- reasoning: Methodology explicitly states v and δ are clamped to measurements while ψ̇ is predicted.
- evidence:
  > The model under attack is the existing CommonRoad KS predictor: `ψ̇ = v · tan(δ) / L`, with `v` and `δ` clamped to measurements (speed-known lateral-only mode).

### regime-breakdown-present
- result: `False`
- reasoning: Only an aggregate plus a narrative speed-band remark; no per-regime (straight/cornering/transient) table or chart of the chosen metric.
- evidence:
  > Improvement is concentrated in the 5–20 m/s band (≈ 12–20 % RMSE reduction); at highway speed (>30 m/s) the gain shrinks to ~2 %.

### methodology-consistent
- result: `True`
- reasoning: A single fixed activity mask and sample/segment count is declared up-front and the Shapley table evaluates every subset under that same definition.
- evidence:
  > activity-masked (v ≥ 5 m/s **and** |ψ̇_truth| ≥ 2 deg/s; n ≈ 85 300 samples across 120 segments)

### attribution-coherent
- result: `True`
- value: `0.02`, threshold_met: `True`
- reasoning: Shapley credits sum to 0.155+0.056+0.005=0.216 vs total drop 0.215 deg/s, |0.216-0.215|/0.215≈0.005, well below 0.15.
- evidence:
  > | **C1 (effective steer-ratio α)** | **+0.155** | **71.9 %** |
  > Cumulative (waterfall) accounting agrees to within 1 percentage-point — most of the value is in α

### honest-regression-flagged
- result: `None`
- reasoning: not addressed in report
- evidence: _none_
