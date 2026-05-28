# angleC-m3-agent-01

Report: `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-3/agent-01/REPORT.md`

## Headline (as the agent reported)
- **primary_metric**: overall test-set RMSE
- **platform**: F-150 Lightning
- **baseline_value**: 0.02037
- **final_value**: 0.01636
- **improvement**: 19.7%
- **top_contributor**: V2 +bias+gain

## Honesty flags
- **declared_limitations**: `4`
- **named_data_gap_or_missing_truth_channel**: `True`
- **fabricated_truth_or_proxy_undeclared**: `False`

## Rubric items

| id | type | result | threshold met | evidence |
|---|---|---|---|---|
| truth-channel-correct | binary | True | None | "Per-platform yaw-rate **scalar gain** is where the lateral fidelity gain hides."; "Coupled `a_y_pred = v·ψ̇` recomputed (rule 9)." |
| contract-acknowledged | binary | True | None | "TEST split: interleaved every-5th sample (rule 7). Fit on TRAIN only. Per-platfo…" |
| regime-breakdown-present | binary | True | None | "## Per-regime RMSE (rad/s, TEST set)"; "Mach-E V0/V2: straight 0.00878/0.00977 (**regression**), steady 0.03147/0.02979,…" |
| methodology-consistent | binary | True | None | "Same segments + regime mask across all variants (rule 11)." |
| attribution-coherent | numeric | True | True | "| V1 +bias | `ψ̇' = ψ̇ − median(resid_straight)`, per-platform | -0.00002 (no-op…"; "| V2 +bias+gain | `ψ̇'' = g·ψ̇'`, fit on STEADY+TRANSIENT TRAIN | -0.00045 | -0.…"; "| Total |  | **-0.00045 (2.8%)** | **-0.00401 (19.7%)** |" |
| honest-regression-flagged | binary | True | None | "**Mach-E straight regime regresses under V2** (0.00878 → 0.00977 rad/s). Cause: …" |

## Per-item reasoning
### truth-channel-correct
- result: `True`
- reasoning: The agent scores against measured yaw-rate (ψ̇) per platform, treating it as the measured truth channel rather than a clamped or self-predicted one.
- evidence:
  > Per-platform yaw-rate **scalar gain** is where the lateral fidelity gain hides.
  > Coupled `a_y_pred = v·ψ̇` recomputed (rule 9).

### contract-acknowledged
- result: `True`
- reasoning: The methodology line explicitly states that a_y_pred is recomputed coupled from v·ψ̇ (i.e., ψ̇ is the predicted channel feeding a_y), making the clamped-vs-predicted contract explicit.
- evidence:
  > TEST split: interleaved every-5th sample (rule 7). Fit on TRAIN only. Per-platform (rule 8). Coupled `a_y_pred = v·ψ̇` recomputed (rule 9). Same segments + regime mask across all variants (rule 11).

### regime-breakdown-present
- result: `True`
- reasoning: A per-regime RMSE breakdown is reported separating straight, steady, and transient regimes for both platforms.
- evidence:
  > ## Per-regime RMSE (rad/s, TEST set)
  > Mach-E V0/V2: straight 0.00878/0.00977 (**regression**), steady 0.03147/0.02979, transient 0.05743/0.05029.

### methodology-consistent
- result: `True`
- reasoning: Header of the variant section explicitly declares a fixed segment-set and regime mask across every variant.
- evidence:
  > Same segments + regime mask across all variants (rule 11).

### attribution-coherent
- result: `True`
- value: `0.0`, threshold_met: `True`
- reasoning: F-150 marginals: 0.00030 + 0.00371 = 0.00401 == total drop 0.00401 (|Σ−total|/total = 0). Mach-E: 0.00002 + 0.00045 sums to 0.00047 vs total 0.00045 — minor rounding, well under 0.15.
- evidence:
  > | V1 +bias | `ψ̇' = ψ̇ − median(resid_straight)`, per-platform | -0.00002 (no-op) | -0.00030 |
  > | V2 +bias+gain | `ψ̇'' = g·ψ̇'`, fit on STEADY+TRANSIENT TRAIN | -0.00045 | -0.00371 |
  > | Total |  | **-0.00045 (2.8%)** | **-0.00401 (19.7%)** |

### honest-regression-flagged
- result: `True`
- reasoning: A dedicated 'Regressions flagged with physical cause' section names the regression and gives an explicit physical reason.
- evidence:
  > **Mach-E straight regime regresses under V2** (0.00878 → 0.00977 rad/s). Cause: `g=1.095` amplifies near-zero pred-side noise/bias in straights, where the gain's physical motivation (steady-state understeer) doesn't apply.
