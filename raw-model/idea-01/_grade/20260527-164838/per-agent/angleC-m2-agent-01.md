# angleC-m2-agent-01

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-2/agent-01/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: Yaw-rate RMSE
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.924
- **final_value**: 0.892
- **improvement**: 3.5% reduction
- **top_contributor**: V2 steering-gain k

## Honesty flags
- **declared_limitations**: `6`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "`yaw_rate_meas_rads` is the **measured** IMU yaw rate from the rlog; `yaw_rate_p…" |
| contract-acknowledged | binary | True | None | "**Operating contract (rule 5):** `v_mps` and `delta_road_rad` clamped to measure…" |
| regime-breakdown-present | binary | True | None | "| Variant | Fit scope | Overall | Δ vs prev | Straight | Steady | Transient |" |
| methodology-consistent | binary | True | None | "**Regime mask** (fixed): straight `|δ_road| < 0.5°`; transient (not straight ∧ 1…" |
| attribution-coherent | numeric | True | True | "| V1 constant yaw bias | per-platform (1 scalar = +0.00075 rad/s) | 0.9248 | -0.…"; "**Yaw-rate RMSE 0.924 → 0.892 deg/s on test as a generalising per-platform fit (…" |
| honest-regression-flagged | binary | True | None | "1. V2 hurts straight (0.497 → 0.534). Gain on near-zero predictor amplifies nois…"; "2. V2/V3 hurt `a_y` overall and in steady cornering (0.338 → 0.363). `a_y = v·ψ̇…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Agent explicitly names the scored channel as the measured IMU yaw rate from the rlog dataset.
- evidence:
  > `yaw_rate_meas_rads` is the **measured** IMU yaw rate from the rlog; `yaw_rate_pred_rads` is KS-model output.

### contract-acknowledged
- result: `True`
- reasoning: Explicit clamped-vs-predicted statement appears in the Setup/methodology section.
- evidence:
  > **Operating contract (rule 5):** `v_mps` and `delta_road_rad` clamped to measured at every integrator step; only lateral states predicted.

### regime-breakdown-present
- result: `True`
- reasoning: The variant ladder table breaks out RMSE by straight/steady/transient regimes.
- evidence:
  > | Variant | Fit scope | Overall | Δ vs prev | Straight | Steady | Transient |

### methodology-consistent
- result: `True`
- reasoning: A fixed regime mask is declared up front and the same segment columns (Straight/Steady/Transient) are used across every variant in both tables.
- evidence:
  > **Regime mask** (fixed): straight `|δ_road| < 0.5°`; transient (not straight ∧ 1-s rolling σ(δ_road) > 0.3°); else steady. Counts: straight 774k / steady 97k / transient 42k.

### attribution-coherent
- result: `True`
- value: `0.006`, threshold_met: `True`
- reasoning: Marginal Δ column sums V0→V3: -0.0004 + 0.0321 + 0.0031 = 0.0348, total drop = 0.924-0.892 = 0.032; |0.0348-0.032|/0.032 ≈ 0.087 < 0.15 (well under threshold).
- evidence:
  > | V1 constant yaw bias | per-platform (1 scalar = +0.00075 rad/s) | 0.9248 | -0.0004 | 0.4945 | 1.4294 | 3.0524 |
  > **Yaw-rate RMSE 0.924 → 0.892 deg/s on test as a generalising per-platform fit (V2+V3), a 3.5% reduction.

### honest-regression-flagged
- result: `True`
- reasoning: Dedicated 'Regressions flagged' section lists regressions with explicit physical causes (gain on near-zero predictor; a_y=v·ψ̇ coupling).
- evidence:
  > 1. V2 hurts straight (0.497 → 0.534). Gain on near-zero predictor amplifies noise. Mitigation candidate: regime-conditional gain.
  > 2. V2/V3 hurt `a_y` overall and in steady cornering (0.338 → 0.363). `a_y = v·ψ̇` coupling: scaling ψ̇ overshoots measured a_lat.
