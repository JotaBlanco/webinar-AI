# angleE-m4-agent-03

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-E/module-4/agent-03/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: RMSE(yaw_rate_resid_rads)
- **platform**: FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01613
- **final_value**: 0.01663 rad/s
- **improvement**: −0.0005, i.e. worse
- **top_contributor**: V1 KS recalibrated + per-segment straight-line bias

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "Truth channel: `yaw_rate_meas_rads` (measured, present on Ford only)." |
| contract-acknowledged | binary | True | None | "Inputs `v_mps` and `delta_road_rad` are **clamped to measured** (`clamp_v_to_mea…" |
| regime-breakdown-present | binary | True | None | "| V0 baseline (sim.csv as-is) | 0.01613 | 0.00877 | 0.03173 | 0.05680 | — | refe…" |
| methodology-consistent | binary | True | None | "Lateral metric: `RMSE(yaw_rate_resid_rads)` overall and per regime (`|δ| < 0.01`…" |
| attribution-coherent | numeric | True | True | "Total V0→V3: **−0.00051**. Sum of marginals: **−0.00051**. Reconcile gap **0.0 %…" |
| honest-regression-flagged | binary | True | None | "**V2 vs V1 — physical cause.** The openpilot prior C_αf=286 551 / C_αr=355 912 N…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: Names the scored channel and identifies it as measured on the Ford platform.
- evidence:
  > Truth channel: `yaw_rate_meas_rads` (measured, present on Ford only).

### contract-acknowledged
- result: `True`
- reasoning: Explicitly states which channels are clamped to measured and which is the predicted/scored channel.
- evidence:
  > Inputs `v_mps` and `delta_road_rad` are **clamped to measured** (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Speed-state agreement is zero by construction and not the metric.

### regime-breakdown-present
- result: `True`
- reasoning: Variant table has per-regime columns (straight/steady/transient) for the chosen metric.
- evidence:
  > | V0 baseline (sim.csv as-is) | 0.01613 | 0.00877 | 0.03173 | 0.05680 | — | reference |

### methodology-consistent
- result: `True`
- reasoning: A single regime-mask declaration and metric definition is stated upfront and used across the variant table; sibling regime-contrast table notes 'same regime mask'.
- evidence:
  > Lateral metric: `RMSE(yaw_rate_resid_rads)` overall and per regime (`|δ| < 0.01` straight; `≥0.01 & |dδ/dt| < 0.05` steady; else transient, dt=0.02 s).

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: Marginal column and total drop both present and exactly reconcilable; gap is 0% which is well under 0.15.
- evidence:
  > Total V0→V3: **−0.00051**. Sum of marginals: **−0.00051**. Reconcile gap **0.0 %** (well inside 15 %).

### honest-regression-flagged
- result: `True`
- reasoning: V2 and V3 regressions explicitly flagged with physical/numerical causes.
- evidence:
  > **V2 vs V1 — physical cause.** The openpilot prior C_αf=286 551 / C_αr=355 912 N/rad implies a stiff understeering linear bicycle. On these segments the simple `tan(δ)·v/L` (V1) is closer to truth in steady cornering than the gain-shaped ST. Switching to V2 imports the wrong understeer assumption.
