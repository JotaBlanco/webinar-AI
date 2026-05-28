# angleE-m4-agent-02

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-4/agent-02/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: RMSE(yaw_rate_resid_rads)
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01613
- **final_value**: 0.01663
- **improvement**: Total drop V0 → V3: −0.000508 rad/s (the ladder net-regresses)
- **top_contributor**: V1 KS recalibrated (bias-subtracted)

## Honesty flags
- **declared_limitations**: `4`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "`yaw_rate_meas_rads` is measured truth (gyro)."; "the only metric is `RMSE(yaw_rate_resid_rads)`." |
| contract-acknowledged | binary | True | None | "`v_mps` and `delta_road_rad` are clamped to measured inputs (`clamp_v_to_measure…"; "Speed-state agreement is zero by construction; the only metric is `RMSE(yaw_rate…" |
| regime-breakdown-present | binary | True | None | "| Variant | Overall RMSE (rad/s) | straight | steady | transient | Marginal Δ ov…" |
| methodology-consistent | binary | True | None | "## Variant ladder (strict-marginal accounting, fixed order V0 → V3)"; "| Variant | Overall RMSE (rad/s) | straight | steady | transient | Marginal Δ ov…" |
| attribution-coherent | numeric | True | True | "Total drop V0 → V3: **−0.000508 rad/s** (the ladder net-regresses). Sum of margi…"; "Marginal Δ overall" |
| honest-regression-flagged | binary | True | None | "**V2 worsens every regime vs V1 and vs V0.** Physical reason: openpilot's canoni…"; "**V3 worsens further (marginally) vs V2.** Fit returned `C_αf = C_αr = 150,000` …" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Agent explicitly names yaw_rate_meas_rads as measured truth (gyro) and scores against the yaw-rate residual.
- evidence:
  > `yaw_rate_meas_rads` is measured truth (gyro).
  > the only metric is `RMSE(yaw_rate_resid_rads)`.

### contract-acknowledged
- result: `True`
- reasoning: Operating contract section explicitly states which channels are clamped to measured truth vs which is the predicted-vs-measured scoring channel.
- evidence:
  > `v_mps` and `delta_road_rad` are clamped to measured inputs (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`).
  > Speed-state agreement is zero by construction; the only metric is `RMSE(yaw_rate_resid_rads)`.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks out RMSE by straight / steady / transient regimes.
- evidence:
  > | Variant | Overall RMSE (rad/s) | straight | steady | transient | Marginal Δ overall | Attribution |

### methodology-consistent
- result: `True`
- reasoning: Single variant table with consistent regime columns and metric definition (RMSE rad/s) applied across V0–V3.
- evidence:
  > ## Variant ladder (strict-marginal accounting, fixed order V0 → V3)
  > | Variant | Overall RMSE (rad/s) | straight | steady | transient | Marginal Δ overall | Attribution |

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Marginal column present (−0.00143, +0.00184, +0.00011 sums to −0.000508 = total drop exactly), so |Σ marginals − total|/|total| = 0 < 0.15.
- evidence:
  > Total drop V0 → V3: **−0.000508 rad/s** (the ladder net-regresses). Sum of marginals matches total drop exactly (accounting is consistent; the 15% tolerance is degenerate when total is negative).
  > Marginal Δ overall

### honest-regression-flagged
- result: `True`
- reasoning: Dedicated Regression flags section names V2 and V3 regressions with explicit physical causes (stiff ST prior; L-BFGS-B optimizer stall).
- evidence:
  > **V2 worsens every regime vs V1 and vs V0.** Physical reason: openpilot's canonical priors `C_αf = 286,551`, `C_αr = 355,912` N/rad produce a `K_us` that under-rotates the model relative to truth on cornering samples. The ST prior is stiffer than the Mach-E's actual cornering compliance on this segment set.
  > **V3 worsens further (marginally) vs V2.** Fit returned `C_αf = C_αr = 150,000` N/rad — **exactly the L-BFGS-B initial guess**
