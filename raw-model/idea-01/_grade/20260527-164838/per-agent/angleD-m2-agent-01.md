# angleD-m2-agent-01

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-D/module-2/agent-01/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: overall RMSE [rad/s]
- **platform**: FORD_MUSTANG_MACH_E_MK1 (Mach-E MK1)
- **baseline_value**: 0.01192
- **final_value**: 0.00993
- **improvement**: −0.00199 (−16.7%)
- **top_contributor**: V1 KS recalibrated, canonical L, per-segment straight bias

## Honesty flags
- **declared_limitations**: `4`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "**Truth channel:** `yaw_rate_meas_rads` is *measured* truth — decoded from the r…" |
| contract-acknowledged | binary | True | None | "**Operating contract:** speed-known, lateral-only (`clamp_v_to_measured=True`, `…" |
| regime-breakdown-present | binary | True | None | "| Variant | overall RMSE [rad/s] | straight | steady | transient | attribution Δ…" |
| methodology-consistent | binary | True | None | "**Sample:** 20 segments, deterministic stride over 315 available Mach-E `sim.csv…"; "**Residual under test:** `yaw_rate_pred − yaw_rate_meas` (rad/s)." |
| attribution-coherent | numeric | True | True | "**V1 is the only positive contributor on overall RMSE.** It contributes the whol…"; "| V1 KS recalibrated, canonical L, per-segment straight bias | **0.00993** | 0.0…" |
| honest-regression-flagged | binary | True | None | "| V2 Linear ST, prior C_α (openpilot-canonical)              | 0.01155     | 0.0…"; "**V2 over-shrinks gain.** Prior C_α makes K_us > 0 in a regime where the in-CSV …" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Report explicitly names yaw_rate_meas_rads as measured truth and cites the rlog IMU source via Ford DBC.
- evidence:
  > **Truth channel:** `yaw_rate_meas_rads` is *measured* truth — decoded from the rlog IMU via the Ford party DBC (Mach-E is a first-class openpilot port; SKILL.md confirms Tesla has no decoded IMU yaw, Ford does).

### contract-acknowledged
- result: `True`
- reasoning: Methodology explicitly states which channels are clamped to truth (v and delta) vs predicted (yaw rate).
- evidence:
  > **Operating contract:** speed-known, lateral-only (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`, per SKILL.md).

### regime-breakdown-present
- result: `True`
- reasoning: Variant table breaks RMSE out by straight/steady/transient regimes.
- evidence:
  > | Variant | overall RMSE [rad/s] | straight | steady | transient | attribution Δ vs prev |

### methodology-consistent
- result: `True`
- reasoning: Single fixed sample and a single residual/metric definition declared in the header are applied to every variant in the table.
- evidence:
  > **Sample:** 20 segments, deterministic stride over 315 available Mach-E `sim.csv` files; 57,987 rows total.
  > **Residual under test:** `yaw_rate_pred − yaw_rate_meas` (rad/s).

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Total drop V0->V1 = 0.00199; V1 is credited the full 0.00199 with later variants reported as regressions, so |Σ marginal drops − total drop|/total drop ≈ 0 (well below 0.15).
- evidence:
  > **V1 is the only positive contributor on overall RMSE.** It contributes the whole 0.00199 rad/s overall improvement (−16.7% vs V0).
  > | V1 KS recalibrated, canonical L, per-segment straight bias | **0.00993** | 0.00430 | 0.01683 | 0.03948 | **−0.00199 (−16.7%)** |

### honest-regression-flagged
- result: `True`
- reasoning: V2 and V4 are explicitly labeled as regressions in the variant table and each is given a physical cause (over-shrunk gain via stiff Cα prior; ridge fitting noise on over-corrected residuals).
- evidence:
  > | V2 Linear ST, prior C_α (openpilot-canonical)              | 0.01155     | 0.00350 | 0.02088 | 0.04681 | +0.00162 *(regression)* |
  > **V2 over-shrinks gain.** Prior C_α makes K_us > 0 in a regime where the in-CSV KS prediction (no slip term) was already accurate; the ST gain at v=20 m/s is ~18% lower than KS, so steady and transient RMSE grow.
