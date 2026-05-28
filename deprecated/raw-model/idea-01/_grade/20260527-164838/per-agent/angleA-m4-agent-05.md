# angleA-m4-agent-05

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-4/agent-05/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: RMSE overall (rad/s)
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.02570
- **final_value**: 0.02463
- **improvement**: V0→V3 total RMSE drop = **0.00064 rad/s** (2.5% reduction). Largest single improvement comes from **V1 alone** (0.00107 rad/s, 4.1%)
- **top_contributor**: V1

## Honesty flags
- **declared_limitations**: `4`
- **named_data_gap_or_missing_truth_channel**: `False`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "**Truth channel:** `yaw_rate_meas_rads` — the IMU-**measured** yaw rate decoded …" |
| contract-acknowledged | binary | True | None | "**Speed-known contract:** both `v_mps` and `delta_road_rad` are **clamped** to t…" |
| regime-breakdown-present | binary | True | None | "| Variant | Description | RMSE overall (rad/s) | Straight | Steady | Transient |…" |
| methodology-consistent | binary | True | None | "**Methodology consistency:** the **same segment set** and **same regime mask** a…" |
| attribution-coherent | numeric | True | True | "Accounting scheme: **strict marginal** in fixed order V0→V1→V2→V3. The ΔRMSE col…" |
| honest-regression-flagged | binary | True | None | "**V1 → V2 (+0.00068 rad/s, REGRESSION).** Swapping KS for linear-ST steady-state…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report explicitly names the measured IMU yaw rate as the scored truth channel and cites the rlog as source.
- evidence:
  > **Truth channel:** `yaw_rate_meas_rads` — the IMU-**measured** yaw rate decoded from the rlog, not predicted, not clamped.

### contract-acknowledged
- result: `True`
- reasoning: Methodology explicitly states which channels are clamped vs predicted.
- evidence:
  > **Speed-known contract:** both `v_mps` and `delta_road_rad` are **clamped** to the measured signal at every integrator step. The lateral state is what the model **predicts** under that clamped input.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table includes per-regime columns (Straight, Steady, Transient) for the chosen metric.
- evidence:
  > | Variant | Description | RMSE overall (rad/s) | Straight | Steady | Transient | ΔRMSE vs prev |

### methodology-consistent
- result: `True`
- reasoning: Explicit statement of fixed segment set and regime mask across all variants.
- evidence:
  > **Methodology consistency:** the **same segment set** and **same regime mask** are held constant across every variant row. The only thing that changes between rows is the prediction model.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Sum of marginal drops (-0.00107 + 0.00068 - 0.00025 = -0.00064) equals total drop (-0.00064); ratio ~0, well under 0.15.
- evidence:
  > Accounting scheme: **strict marginal** in fixed order V0→V1→V2→V3. The ΔRMSE column is `RMSE(V_i) − RMSE(V_{i-1})` (negative = improvement, positive = regression). `|Σmarg − total|/total ≈ 0` — attribution coherent.

### honest-regression-flagged
- result: `True`
- reasoning: V2 explicitly flagged as regression with physical cause; V4 also dropped as flagged regression with stated reason.
- evidence:
  > **V1 → V2 (+0.00068 rad/s, REGRESSION).** Swapping KS for linear-ST steady-state with openpilot prior `C_α` **worsens** overall RMSE. ... **Physical cause:** the openpilot Mach-E `C_α` prior is stiffer than the actual tyres want.
