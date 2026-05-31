# REPORT — module-1 / agent-10

## Headline numerical result

Yaw-rate RMSE (rad/s) and distance-resampled CTE RMSE (m), V0 baseline vs V1 (per-platform fit), computed against `data/sim/` truth via the same `predict(sim_df, platform)` contract grading will use (input read from `data/sim-only/`):

| Platform | V0 yaw RMSE | V1 yaw RMSE | Δ | V0 CTE | V1 CTE | Δ |
|---|---|---|---|---|---|---|
| FORD_MUSTANG_MACH_E_MK1 | 0.01650 | **0.01392** | -15.6% | 148.0 m | **126.9 m** | -14.3% |
| FORD_F_150_LIGHTNING_MK1 | 0.01941 | **0.01270** | -34.6% | 157.5 m | **61.9 m** | -60.7% |
| HYUNDAI_IONIQ_5 | 0.01755 | **0.00969** | -44.8% | 247.4 m | **121.0 m** | -51.1% |
| TESLA_MODEL_3 | — (no truth) | passthrough V0 | — | — | — | — |

CTE numbers look large because the absolute trajectory is integrated from yaw and small constant biases produce unbounded heading drift over multi-minute segments — V1 still cuts it materially.

## What I implemented

- **V1 (all trained platforms):** steady-state bicycle with understeer gradient, `yaw_ss = v · δ_eff / (L_eff + K_us · v²)`. Linear regression on `v·δ = L·yaw + K_us·yaw·v² + v·d0` over every Ford/Hyundai segment gave per-platform `(L_eff, K_us, d0)`. Added a first-order LP1 lag on `δ` (`τ_steer ≈ 0.05 s`) and a small one on yaw (`τ_yaw ≤ 0.02 s`), sweep-selected.
- **Tesla:** no truth channel in workshop data, so `predict` passes through the supplied V0 `yaw_rate_pred_rads` (KS).
- **Trajectory:** trapezoidal integration of predicted yaw + measured `v_mps` → `(x_m, y_m, ψ)`.

Ship dir: `final-model/` — `predict.py`, `manifest.json`, `coeffs.json`. Fit + local-grade scripts in `scripts/`.

## Painful absence in the harness

No `score-model/` skill or pre-wired grader stub. I had to reverse-engineer the schema by reading sim/ and sim-only/ CSVs and write `scripts/grade_local.py` from scratch — including the distance-resampled CTE definition (I picked uniform 1 m arc-length resampling + point-wise Euclidean; the real grader may use perpendicular distance to nearest segment, which would give smaller numbers but the same V1-vs-V0 *ratio*). Probably 10 min of the 45 went to this.

## What the rules almost prevented (and I noticed)

I almost reached for `module-2`/`webinar-meta` to look for the canonical CTE formula and Tesla L/K_us priors. Stopped myself, documented the assumption (uniform-arc-length point-wise distance), and used Tesla's V0 passthrough instead of inventing a transfer prior.

## Most surprising thing learned

The KS baseline was already pretty good on the lightweight EVs but *catastrophic* on the F-150 Lightning — V0 wheelbase L=3.70 is geometrically right, but the fitted `L_eff` is 3.83 and `K_us` is the largest of the three, suggesting the rear-biased truck loads up the rear tyres enough that the kinematic geometry alone is 35% off on yaw. Single linear regression on `(yaw, yaw·v², v)` recovered the truck-specific compliance without a single ST-rung parameter.
