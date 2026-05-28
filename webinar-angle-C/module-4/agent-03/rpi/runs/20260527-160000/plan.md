# Plan — locked variant ladder

Scoring discipline (from `skills/ablation-study`):
- Interleaved 4/1 train/test split (every 5th sample → test). All reported RMSE is test-only.
- Same segment set across variants (all sim.csv under platform).
- Same regime mask as baseline-residual.
- Additive monotone variants. Per-platform fits (NOT per-segment — per-segment would memorise per-route sensor zero).

## Ladder (fixed order)

| V  | adds                                  | hypothesis                                                                                 | falsifiable test                                                |
|----|---------------------------------------|--------------------------------------------------------------------------------------------|-----------------------------------------------------------------|
| V0 | nothing                               | residual as-is from sim                                                                    | matches `evals/baseline_rmse.py`                                |
| V1 | constant `delta_offset` (per-platform)| straight-line yaw-rate residual is dominated by a steering-zero offset                     | if straight-regime RMSE doesn't drop, the offset was noise      |
| V2 | understeer gradient `K_us` (per-plat) | KS over-predicts yaw at speed because it omits side-slip; corrected via linear bicycle      | if steady-cornering RMSE doesn't drop, understeer wasn't the cause |
| V3 | integer sample lag (per-platform)     | measurement / actuator pipeline introduces a small phase lag                                | if transient RMSE doesn't drop, lag wasn't the limiting term    |

Lock: order is V0 → V1 → V2 → V3. Don't reorder based on results.
