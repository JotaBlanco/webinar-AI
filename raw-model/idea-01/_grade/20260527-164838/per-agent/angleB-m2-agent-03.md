# angleB-m2-agent-03

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-2/agent-03/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: RMSE of `yaw_rate_resid_rads = ψ̇_pred − ψ̇_meas`, broken out by regime, in **mrad/s**
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 16.127
- **final_value**: 14.202
- **improvement**: 1.924 mrad/s (11.9%)
- **top_contributor**: V1

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "**Truth channel:** `yaw_rate_meas_rads` — measured from the Ford CAN bus via `op…" |
| contract-acknowledged | binary | True | None | "**Operating contract (speed-known, lateral-only):** `clamp_v_to_measured=True`, …" |
| regime-breakdown-present | binary | True | None | "| Variant | Description | Overall | Straight | Steady | Transient | Marginal |" |
| methodology-consistent | binary | True | None | "**Regime mask** (consistent across all variants):" |
| attribution-coherent | numeric | True | True | "**Total drop V0 → V4:** 1.924 mrad/s (11.9%). **Sum of marginal drops:** 1.924 m…" |
| honest-regression-flagged | binary | True | None | "## Regression: V2 worsened the metric on its own"; "Physical cause: production Cα prior is calibrated for openpilot's lat planner, n…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Agent names a measured CAN-bus channel as truth and explicitly excludes predicted/self-consistency/GPS proxies.
- evidence:
  > **Truth channel:** `yaw_rate_meas_rads` — measured from the Ford CAN bus via `opendbc/ford_lincoln_base_pt`, decoded by `code/adapter_ford_rlog.py`. Not predicted, not self-consistency, not GPS-derived.

### contract-acknowledged
- result: `True`
- reasoning: Explicit clamped-vs-predicted enumeration in the methodology header.
- evidence:
  > **Operating contract (speed-known, lateral-only):** `clamp_v_to_measured=True`, `clamp_delta_to_measured=True`. **Clamped:** `v`, `δ`. **Predicted:** `ψ̇`, `a_y`, `ψ`, `(x,y)`.

### regime-breakdown-present
- result: `True`
- reasoning: Ladder table breaks RMSE out into Straight, Steady, and Transient regimes per variant.
- evidence:
  > | Variant | Description | Overall | Straight | Steady | Transient | Marginal |

### methodology-consistent
- result: `True`
- reasoning: A single regime-mask declaration is stated as fixed across every variant on the ladder.
- evidence:
  > **Regime mask** (consistent across all variants):

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Sum of marginal drops (-1.984+0.604-0.430-0.114 = -1.924) equals the total drop of 1.924 mrad/s exactly; |Σ-total|/total = 0 < 0.15.
- evidence:
  > **Total drop V0 → V4:** 1.924 mrad/s (11.9%). **Sum of marginal drops:** 1.924 mrad/s.

### honest-regression-flagged
- result: `True`
- reasoning: Variant V2 is explicitly flagged as a regression with a physical cause (shipped Cα prior near neutral-steer under-rotates at speed).
- evidence:
  > ## Regression: V2 worsened the metric on its own
  > Physical cause: production Cα prior is calibrated for openpilot's lat planner, not for residual minimisation; small K_us mismatch is amplified in cornering.
