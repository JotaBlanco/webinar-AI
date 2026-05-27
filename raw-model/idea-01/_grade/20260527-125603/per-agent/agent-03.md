# agent-03

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-03/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: RMSE of yaw-rate prediction (rad/s), evaluated on a held-out 20 % segment-level test split, pooled across both Ford platforms
- **platform**: pooled across both Ford platforms (Mustang Mach-E MK1 and F-150 Lightning MK1)
- **baseline_value**: 0.01270 rad/s
- **final_value**: 0.00839 rad/s
- **improvement**: 33.9 %
- **top_contributor**: understeer (K_us)

## Honesty flags
- **declared_limitations**: `6`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "**Primary metric:** RMSE of yaw-rate prediction (rad/s), evaluated on a held-out…"; "Only Ford segments were used because the Tesla simdata has no measured-yaw-rate …" |
| contract-acknowledged | binary | False | None | _none_ |
| regime-breakdown-present | binary | False | None | _none_ |
| methodology-consistent | binary | True | None | "All three parameters were fit on the **train** split (≈80 % of segments, hashed …" |
| attribution-coherent | numeric | True | True | "**Scheme A — marginal / sequential ablation** (drop in test-set RMSE when this v…"; "| bias        | −5.0 % | −2.8 % |"; "| ratio       | +30.3 % | +69.2 % |"; "| understeer (K_us) | +74.7 % | +33.6 % |" |
| honest-regression-flagged | binary | True | None | "**Steering-bias correction by itself made things slightly worse** on both platfo…" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: The agent explicitly names yaw-rate as the scored channel and identifies it as a measured truth channel from Ford simdata, excluding Tesla because it lacks one.
- evidence:
  > **Primary metric:** RMSE of yaw-rate prediction (rad/s), evaluated on a held-out 20 % segment-level test split, pooled across both Ford platforms (Mustang Mach-E MK1 and F-150 Lightning MK1) where the dataset includes a measured-yaw-rate truth channel.
  > Only Ford segments were used because the Tesla simdata has no measured-yaw-rate truth channel (Tesla rlogs lack a decoded IMU on the open DBC).

### contract-acknowledged
- result: `False`
- reasoning: The report describes which parameters are fit and the prediction equations used, but does not explicitly state which channels are clamped to truth versus predicted by the model.
- evidence: _none_

### regime-breakdown-present
- result: `False`
- reasoning: Errors are broken out by platform (Mach-E vs F-150) but not by driving regime (straight / cornering / transient); the report only notes regime stratification as future work ('A separate analysis would benefit from stratifying by `|a_y|`').
- evidence: _none_

### methodology-consistent
- result: `True`
- reasoning: The same test-split RMSE metric and same pooled Ford segment set is used across all variants V0-V3 in the headline and attribution tables.
- evidence:
  > All three parameters were fit on the **train** split (≈80 % of segments, hashed deterministically) and the RMSE numbers above are reported on the disjoint **test** split.

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: The sequential marginal shares sum to 100% by construction for both platforms (-5.0+30.3+74.7=100.0; -2.8+69.2+33.6=100.0), so |Σmarginal − total|/total = 0, well below 0.15.
- evidence:
  > **Scheme A — marginal / sequential ablation** (drop in test-set RMSE when this variant is added on top of the previous one, divided by total V0→V3 drop):
  > | bias        | −5.0 % | −2.8 % |
  > | ratio       | +30.3 % | +69.2 % |
  > | understeer (K_us) | +74.7 % | +33.6 % |

### honest-regression-flagged
- result: `True`
- reasoning: The V1 bias step is flagged as a regression with a physical/statistical cause (small near-straight cohort doesn't generalise), and the marginal table shows negative contributions for bias.
- evidence:
  > **Steering-bias correction by itself made things slightly worse** on both platforms. The near-straight cohort used to fit the bias is too small a slice to characterise the true offset, and the rest of the distribution doesn't share the same median.
