# Module 3 v3 — agent-10 report

## Headline result

| metric | V0 | V1 | **shipped (v1-plus-resid)** | Δ vs V1 |
|---|---|---|---|---|
| yaw_rate_rmse (rad/s) | 0.012934 | 0.005874 | **0.005727** | −2.5% |
| cte_rmse (m)          | 163.83   | 56.807   | **54.304**   | −4.4% |

Scored against `data/sim/segments/` (all 1996 segments, ~5.2M samples). All four declared platforms supported; Tesla is a passthrough by design. Preflight passes every gate.

## What I implemented

Three candidates, all `structure: differs-from-v1`:

1. **`v1-plus-resid`** (shipped). Per-platform 7-feature ridge correction added to V1's yaw output. Features (allowlist-only): `v, δ, dδ/dt, a_long, yr_v1, |δ|, sign(yr_v1)·yr_v1²`. Wins both KPIs jointly.
2. **`steer-rate-ff`**. V1 + `k_ff · v · dδ/dt` derivative feedforward — gives V1 a transfer-function zero it didn't have. Scored 0.005832 / 54.46. Most of its gain came from the bias term it absorbed, not from the derivative.
3. **`v1-cte-debiased`**. V1 + per-platform constant yaw offset chosen by minimising *pooled CTE* (not yaw RMSE). 0.005843 / 54.19 — best CTE of the three. Proved that ≥80% of V1's CTE gap is collapsible by one constant per platform; remaining 54 m is genuine per-segment shape noise.

## Most painful absent component

The `assess-candidate-model` skill was listed but the directory was effectively empty for my purposes. I wrote my own scoring/comparison script (`out/score_models.py`) and per-model `assessment.md` by hand. A working `compare-models` skill would also have been useful — comparing per-segment yaw differences candidate-vs-V1 would have told me, for `steer-rate-ff`, that the bias term was doing the real work *before* I ran the pooled score. I had to infer that from the fitted `bias` values being close to the V1 yaw-bias values they were supposed to cancel.

## Things the rules almost let me do

- I almost reached for `yaw_rate_meas_rads` directly inside `predict()` for "just a quick CTE sanity check at runtime" — caught myself because the contract said the column is denied at grading time. Wrote a separate offline fit script instead.
- I considered training the residual learner on `sim-only/segments/` features alongside `sim/segments/` truth to "match the grader's distribution exactly". That's a one-line slip away from leaking truth via path coupling. Kept training and contract-validation in separate scripts.

## Most surprising thing

Despite an R² of only **0.02–0.07**, the 7-feature linear residual learner improved both pooled KPIs by 2.5–4.4%. The reason: V1's residual is heavy in *bias* on Mach-E (−0.00142 rad/s) and IONIQ-5 (−0.00075 rad/s), and even a near-noiseless intercept (one of seven coefficients) is enough to collapse the platform-level yaw bias to zero and recover almost all the CTE drift. The non-bias features only contribute marginally — but the headline KPIs reward bias-cancellation disproportionately because CTE is the distance-integral of yaw error.
