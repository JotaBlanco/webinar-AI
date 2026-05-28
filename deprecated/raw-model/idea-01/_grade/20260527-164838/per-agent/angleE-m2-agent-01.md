# angleE-m2-agent-01

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-2/agent-01/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: yaw_rate_resid_rads = yaw_rate_pred − yaw_rate_meas
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01613
- **final_value**: 0.01469
- **improvement**: −0.00144 rad/s (−8.9 %)
- **top_contributor**: V1 (KS recalib L + per-segment straight-row yaw-gyro bias)

## Honesty flags
- **declared_limitations**: `4`
- **named_data_gap_or_missing_truth_channel**: `False`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "`yaw_rate_meas_rads` is measured truth (rlog IMU, Ford-only). Residual under tes…" |
| contract-acknowledged | binary | True | None | "Speed `v` and steering `δ` are **clamped to measured** under the speed-known ope…" |
| regime-breakdown-present | binary | True | None | "| variant | overall | straight | steady | transient |" |
| methodology-consistent | binary | True | None | "Regime split (fixed thresholds): straight 785 093 rows, steady 106 978, transien…" |
| attribution-coherent | numeric | True | True | "**Sum of marginals vs. total V0 → V3:** −0.00144 + 0.00184 + 0.00010 = +0.00050 …" |
| honest-regression-flagged | binary | True | None | "**V2, V3 regress past V0 on overall and on every regime.** Cause: the Linear ST …" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Agent names the scored channel and identifies it explicitly as measured truth from rlog IMU.
- evidence:
  > `yaw_rate_meas_rads` is measured truth (rlog IMU, Ford-only). Residual under test: `yaw_rate_resid_rads = yaw_rate_pred − yaw_rate_meas`.

### contract-acknowledged
- result: `True`
- reasoning: Explicit statement of which channels are clamped to truth (v, δ) vs the predicted yaw-rate residual.
- evidence:
  > Speed `v` and steering `δ` are **clamped to measured** under the speed-known operating contract (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). The lateral residual is the *only* metric.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks out RMSE per regime (straight, steady, transient) for every variant.
- evidence:
  > | variant | overall | straight | steady | transient |

### methodology-consistent
- result: `True`
- reasoning: A fixed regime split with declared row counts is shared across all variants in the ladder table.
- evidence:
  > Regime split (fixed thresholds): straight 785 093 rows, steady 106 978, transient 21 555.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Sum of marginal drops equals the total drop exactly; coherence ratio is 0, well under 0.15.
- evidence:
  > **Sum of marginals vs. total V0 → V3:** −0.00144 + 0.00184 + 0.00010 = +0.00050 ≈ total V0→V3 (+0.00050). Within 15 %: yes (exact, by construction).

### honest-regression-flagged
- result: `True`
- reasoning: Regressions in V2 and V3 are explicitly flagged with physical causes.
- evidence:
  > **V2, V3 regress past V0 on overall and on every regime.** Cause: the Linear ST understeer correction with openpilot-canonical Cα reduces predicted yaw rate at moderate v, but the actual residual budget in this dataset is dominated by (a) yaw-gyro DC offset in straight rows and (b) genuine transient dynamics the linear model also can't capture.
