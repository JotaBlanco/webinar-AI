# m1-agent-04

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-04/final-model/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: Yaw RMSE V3
- **platform**: FORD_F_150_LIGHTNING_MK1 and FORD_MUSTANG_MACH_E_MK1
- **baseline_value**: 0.01391 rad/s
- **final_value**: 0.00490 rad/s
- **improvement**: -64.8%
- **top_contributor**: V1

## Honesty flags
- **declared_limitations**: `3`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| regime-breakdown-present | binary | False | None | _none_ |
| methodology-consistent | binary | True | None | "XTE is distance-resampled at ds = 1 m, RMSE over all distance samples in all val…"; "All four parameters jointly fit per platform via Nelder-Mead on yaw-rate MSE ove…" |
| attribution-coherent | numeric | True | True | "**V1** — `a * (v/L) tan(delta) / (1 + b v^2)`. Two-param understeer fit. Biggest…"; "**V2** — add constant `delta_off`. Helped Lightning slightly (0.00659 -> 0.00535…"; "**V3 (shipped)** — V2 + first-order lag `tau` on the steering. Helped both; Ligh…" |
| honest-regression-flagged | binary | False | None | "**V2** — add constant `delta_off`. Helped Lightning slightly (0.00659 -> 0.00535…" |

## Per-item reasoning
### regime-breakdown-present
- result: `False`
- reasoning: The report only breaks errors out by platform and by ladder variant, not by driving regime (straight / cornering / transient).
- evidence: _none_

### methodology-consistent
- result: `True`
- reasoning: The ladder uses the same metric definition (yaw-rate RMSE on val, XTE distance-resampled) and the same train/val split across all variants.
- evidence:
  > XTE is distance-resampled at ds = 1 m, RMSE over all distance samples in all val segments.
  > All four parameters jointly fit per platform via Nelder-Mead on yaw-rate MSE over the train split. No leakage: val routes are entirely disjoint from train routes.

### attribution-coherent
- result: `True`
- value: `0.011`, threshold_met: `True`
- reasoning: Lightning sequential drops sum to (0.01391-0.00659)+(0.00659-0.00535)+(0.00535-0.00490)=0.00901, total drop 0.01391-0.00490=0.00901, |diff|/total ≈ 0.0 < 0.15.
- evidence:
  > **V1** — `a * (v/L) tan(delta) / (1 + b v^2)`. Two-param understeer fit. Biggest single jump on Lightning (val 0.01391 -> 0.00659).
  > **V2** — add constant `delta_off`. Helped Lightning slightly (0.00659 -> 0.00535); Mach-E offset fits to noise.
  > **V3 (shipped)** — V2 + first-order lag `tau` on the steering. Helped both; Lightning val 0.00535 -> 0.00490, Mach-E val 0.01583 -> 0.01541.

### honest-regression-flagged
- result: `False`
- reasoning: No regressions are stated in the variant ladder and the report does not include an explicit 'no regressions observed' statement; the Mach-E V2 'fits to noise' comment is not framed as a regression with physical cause.
- evidence:
  > **V2** — add constant `delta_off`. Helped Lightning slightly (0.00659 -> 0.00535); Mach-E offset fits to noise.
