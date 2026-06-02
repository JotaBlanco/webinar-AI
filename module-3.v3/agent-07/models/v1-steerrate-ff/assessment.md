# v1-steerrate-ff — assessment

## Headline (per platform, fitted on first 120 segments)

| platform | V1 yaw | candidate yaw | Δ% | V1 cte | candidate cte | Δ% |
|---|---|---|---|---|---|---|
| Lightning | 0.00592 | 0.00591 | −0.2% | 66.580 | 66.583 | +0.0% |
| Mach-E    | 0.00924 | 0.00921 | −0.3% | 116.565 | 116.572 | +0.0% |
| IONIQ-5   | 0.01255 | 0.01245 | −0.7% |  89.165 |  89.576 | +0.5% |

## Verdict

**Shelved.** The improvement is below noise across the board — well within
the V1 paper's claim that coefficient-level intervention buys "at most a
basis point or two." k_dd went to the edge of the search range on Mach-E
(−0.10) with the sign suggesting an over-anticipation rather than the
hypothesised lag.

## What this rules out

- **A scalar steering-derivative feedforward cannot recover the transient
  residual.** The transient regime has yaw RMSE 0.0164 — a coefficient-scale
  k_dd · ddelta term cannot lower this materially without becoming
  catastrophically wrong in steady regimes.
- The remaining transient residual is **not a missing input-derivative
  feature** — it likely needs a real second-order dynamic model (rung 1) to
  capture the underdamped response V1's first-order lag can't represent.
