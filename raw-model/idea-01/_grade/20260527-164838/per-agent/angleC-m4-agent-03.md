# angleC-m4-agent-03

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-4/agent-03/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: held-out test RMSE
- **platform**: F-150 Lightning
- **baseline_value**: 0.02037
- **final_value**: 0.01499 rad/s
- **improvement**: -26%
- **top_contributor**: V2

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "Per-platform variant ladder on both Fords (Tesla excluded — no truth). Speed-kno…" |
| contract-acknowledged | binary | True | None | "Speed-known lateral-only KS contract held." |
| regime-breakdown-present | binary | True | None | "Per-regime test RMSE (V3): Mach-E 0.00825 / 0.03259 / 0.05974; Lightning 0.00521…" |
| methodology-consistent | binary | True | None | "Interleaved 4/1 train/test split; all RMSE numbers are held-out test RMSE." |
| attribution-coherent | numeric | True | True | "Marginals — Mach-E: V1 -1.3e-5 (regression), V2 -2.4e-4 (regression), V3 +4.1e-5…" |
| honest-regression-flagged | binary | True | None | "V2 improves straight regime (0.00878→0.00828) but worsens steady and transient —…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Agent scores on measured yaw-rate on Fords and explicitly excludes Tesla due to no measured truth channel.
- evidence:
  > Per-platform variant ladder on both Fords (Tesla excluded — no truth). Speed-known lateral-only KS contract held.

### contract-acknowledged
- result: `True`
- reasoning: Speed is clamped to truth, lateral is predicted — explicit KS contract statement.
- evidence:
  > Speed-known lateral-only KS contract held.

### regime-breakdown-present
- result: `True`
- reasoning: Per-regime RMSE breakdown (straight/cornering/transient) is provided for V3.
- evidence:
  > Per-regime test RMSE (V3): Mach-E 0.00825 / 0.03259 / 0.05974; Lightning 0.00521 / 0.02559 / 0.04392.

### methodology-consistent
- result: `True`
- reasoning: Same split, same metric definition declared once for the entire ladder.
- evidence:
  > Interleaved 4/1 train/test split; all RMSE numbers are held-out test RMSE.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Agent reports both marginal drops and total drop, and explicitly computes coherence ≈ 0.00, well under the 0.15 threshold.
- evidence:
  > Marginals — Mach-E: V1 -1.3e-5 (regression), V2 -2.4e-4 (regression), V3 +4.1e-5. Lightning: V1 +2.2e-4, V2 +5.1e-3, V3 +4.2e-5. Attribution-coherence ≈ 0.00 on both (well under 0.15).

### honest-regression-flagged
- result: `True`
- reasoning: Mach-E net regression is flagged with explicit physical causes (over-encoded understeer priors and ST-rung physics dominating transient residual).
- evidence:
  > V2 improves straight regime (0.00878→0.00828) but worsens steady and transient — `C_α` priors already over-encode understeer for steady cornering, and the transient residual is dominated by tyre-relaxation / actuator phase, which is ST-rung physics, not a KS tweak.
