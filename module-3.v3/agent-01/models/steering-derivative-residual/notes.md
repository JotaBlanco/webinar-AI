# steering-derivative-residual

## Formulation
```
y_pred = predict_v1(sim_df, platform).yaw_rate_pred_rads
       + a·(dδ/dt) + b·v·(dδ/dt) + c·sign(δ̇)·sqrt|δ̇| + d
```
per platform; coefficients (a,b,c,d) fit offline against the V1 residual.

## Inputs / state
Inputs: allowlist 8 columns. `dδ/dt` computed via `np.gradient(delta_road_rad, t_s)`. No persistent state.

## Why this attacks V1's residual
V1 has a transient-regime yaw RMSE of 0.01647 rad/s versus 0.00442 in straight rows. The first-order lag (τ ≈ 0.06–0.07 s) is a single-pole approximation of bicycle dynamics it doesn't model. Steering rate `δ̇` and `v · δ̇` are the two leading-order features of that missing transient dynamic. The constant term `d` simultaneously absorbs the small surviving yaw bias responsible for CTE drift.

## Fit procedure
Ridge least-squares (λ=1e-3) on every `data/sim/segments/<platform>/**/sim.csv`, residual = `yaw_rate_meas_rads - predict_v1.yaw_rate_pred_rads`, mask `v > 5 m/s`. Per-platform coefficient solution stored in `predict.py`.

## Why this is `differs-from-v1`
V1's coefficient family controls (steady-state gain, lag time constant, neutral-steering offset) — none of those produce a term proportional to `dδ/dt` independently of the steady-state response. Adding a steering-rate-driven correction is a state-space extension V1 cannot reach.

## Caveats / risks
- Linear features can over- or under-correct in regions sparsely sampled at fit time. Lightning has a near-zero residual everywhere, so its coefficients are tiny and the correction is benign.
- The constant term `d` doubles as a bias correction; it is small relative to `a·δ̇` peaks but dominates the steady-state.
