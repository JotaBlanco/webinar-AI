# agent-01

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-01/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: pooled yaw-rate RMSE on Tesla Model 3
- **platform**: Tesla Model 3
- **baseline_value**: 2.763 deg/s
- **final_value**: 2.547 deg/s
- **improvement**: -7.8 %
- **top_contributor**: C1 (effective steer-ratio α)

## Honesty flags
- **declared_limitations**: `6`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | False | None | "The truth channel is missing."; "I had to fabricate one from the rear wheel-speed differential `(v_RL – v_RR) / t…" |
| contract-acknowledged | binary | True | None | "The model under attack is the existing CommonRoad KS predictor: `ψ̇ = v · tan(δ)…" |
| regime-breakdown-present | binary | False | None | "Improvement is concentrated in the 5–20 m/s band (≈ 12–20 % RMSE reduction); at …" |
| methodology-consistent | binary | True | None | "activity-masked (v ≥ 5 m/s **and** |ψ̇_truth| ≥ 2 deg/s; n ≈ 85 300 samples acro…"; "Each subset's RMSE was evaluated independently" |
| attribution-coherent | numeric | True | True | "| **C1 (effective steer-ratio α)** | **+0.155** | **71.9 %** |"; "| **C2 (understeer Kᵤ)** | **+0.056** | **25.9 %** |"; "| **C3 (lag τ)** | **+0.005** | **2.2 %** |" |
| honest-regression-flagged | binary | None | None | _none_ |

## Per-item reasoning
### truth-channel-correct
- result: `False`
- reasoning: Agent scored against a fabricated wheel-speed-differential proxy, not a measured yaw-rate channel; rubric explicitly excludes derived/fabricated proxies.
- evidence:
  > The truth channel is missing.
  > I had to fabricate one from the rear wheel-speed differential `(v_RL – v_RR) / track_rear` with `track_rear = 1.580 m` (public Tesla M3 spec).

### contract-acknowledged
- result: `True`
- reasoning: Explicitly states which inputs are clamped to measurements and which channel (ψ̇) is predicted by the model.
- evidence:
  > The model under attack is the existing CommonRoad KS predictor: `ψ̇ = v · tan(δ) / L`, with `v` and `δ` clamped to measurements (speed-known lateral-only mode).

### regime-breakdown-present
- result: `False`
- reasoning: Only a narrative speed-band remark is given; no per-regime table or chart breaking out straight/cornering/transient error is presented.
- evidence:
  > Improvement is concentrated in the 5–20 m/s band (≈ 12–20 % RMSE reduction); at highway speed (>30 m/s) the gain shrinks to ~2 %.

### methodology-consistent
- result: `True`
- reasoning: A single activity mask and sample set is declared up front and reused across all 8 subsets of the ladder; metric (RMSE) is consistent across variants.
- evidence:
  > activity-masked (v ≥ 5 m/s **and** |ψ̇_truth| ≥ 2 deg/s; n ≈ 85 300 samples across 120 segments).
  > Each subset's RMSE was evaluated independently

### attribution-coherent
- result: `True`
- value: `0.01`, threshold_met: `True`
- reasoning: Sum of Shapley credits 0.155+0.056+0.005=0.216 vs total drop 0.215 → |0.216-0.215|/0.215 ≈ 0.005, well under 0.15 threshold.
- evidence:
  > | **C1 (effective steer-ratio α)** | **+0.155** | **71.9 %** |
  > | **C2 (understeer Kᵤ)** | **+0.056** | **25.9 %** |
  > | **C3 (lag τ)** | **+0.005** | **2.2 %** |

### honest-regression-flagged
- result: `None`
- reasoning: Report neither shows a regression row with physical cause nor an explicit 'no regressions observed' statement; not addressed.
- evidence: _none_
