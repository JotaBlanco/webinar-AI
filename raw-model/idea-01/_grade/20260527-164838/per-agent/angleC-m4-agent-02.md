# angleC-m4-agent-02

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-4/agent-02/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: overall yaw-rate RMSE
- **platform**: FORD_MUSTANG_MACH_E_MK1 (Mustang Mach-E MK1, 315 segments, 913 626 samples; test fold 182 725 via interleaved every-5th split)
- **baseline_value**: 0.01613
- **final_value**: 0.01557
- **improvement**: -3.5% overall, **-10% on transient cornering**, -6% on steady
- **top_contributor**: V3 L_eff fit (L_eff=2.793 m)

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `False`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "**Measured-truth statement**: scored against `yaw_rate_meas_rads` (openpilot IMU…" |
| contract-acknowledged | binary | True | None | "**Clamped-vs-predicted**: speed-known lateral-only mode — `v` and `δ` clamped to…" |
| regime-breakdown-present | binary | True | None | "| Variant | overall | straight | steady | transient | marginal |" |
| methodology-consistent | binary | True | None | "## Variant ladder (per-platform, interleaved test fold)"; "All variants per-platform (one scalar / one integer each)." |
| attribution-coherent | numeric | True | True | "Attribution coherence err = 0.0000 (<0.15). Σ marginals = total drop = -0.00055 …" |
| honest-regression-flagged | binary | True | None | "**V1 bias removal**: -0.00001 rad/s. Train median residual (+0.00075) is small a…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Agent explicitly names the measured channel (yaw_rate_meas_rads from openpilot IMU on CAN) and cites the source.
- evidence:
  > **Measured-truth statement**: scored against `yaw_rate_meas_rads` (openpilot IMU yaw rate on CAN, Ford-only).

### contract-acknowledged
- result: `True`
- reasoning: Explicit clamped-vs-predicted statement: v and δ clamped to measured, lateral states predicted.
- evidence:
  > **Clamped-vs-predicted**: speed-known lateral-only mode — `v` and `δ` clamped to measured, lateral states predicted via `ψ̇ = v·tan(δ_road)/L`.

### regime-breakdown-present
- result: `True`
- reasoning: Variant ladder table breaks out RMSE by straight / steady / transient regimes.
- evidence:
  > | Variant | overall | straight | steady | transient | marginal |

### methodology-consistent
- result: `True`
- reasoning: Single ladder with shared fold and shared regime columns applied to every variant; consistent methodology in header/caption.
- evidence:
  > ## Variant ladder (per-platform, interleaved test fold)
  > All variants per-platform (one scalar / one integer each).

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Agent explicitly computes the coherence error as 0.0000, well below the 0.15 threshold, with marginal column and total drop both present.
- evidence:
  > Attribution coherence err = 0.0000 (<0.15). Σ marginals = total drop = -0.00055 rad/s.

### honest-regression-flagged
- result: `True`
- reasoning: Regressions section explicitly flags V1 and V3-straight-side-effect with physical causes.
- evidence:
  > **V1 bias removal**: -0.00001 rad/s. Train median residual (+0.00075) is small and biased the test predictions the wrong way in the straight regime. Physical cause: the V0 residual is already near-zero-mean; no real DC IMU offset to remove on this platform.
