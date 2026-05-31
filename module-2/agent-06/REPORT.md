# Module-2 Agent-06 — Lateral Fidelity Report

## Headline result

Scored on `data/sim/segments/` (1215 valid segments across Ford F-150 Lightning, Ford Mustang Mach-E, Hyundai Ioniq 5 — Tesla skipped by score-model because its sim.csv carries `psi_dot_rads` instead of `yaw_rate_meas_rads`; verified separately):

| metric              | V0 baseline | V1 final  | delta   |
|---------------------|------------:|----------:|--------:|
| yaw_rate_rmse rad/s | 0.016773    | 0.008625  | -48.6%  |
| cte_rmse m          | 218.16      | 105.24    | -51.7%  |

Tesla Model-3 yaw RMSE (V0 passthrough vs `psi_dot_rads` truth on 30 segments) = 1.5e-7 rad/s — synthetic Tesla truth IS the KS formula.

## Per-platform on dev (V1)

| platform                  | yaw_rmse | cte_rmse | bias_frac |
|---------------------------|---------:|---------:|----------:|
| FORD_F_150_LIGHTNING_MK1  | 0.00642  | 63.3     | 0.01      |
| FORD_MUSTANG_MACH_E_MK1   | 0.00953  | 121.7    | 0.00      |
| HYUNDAI_IONIQ_5           | 0.00874  | 107.2    | 0.00      |
| TESLA_MODEL_3 (V0 pass.)  | ~1e-7    | ~1e-4    | n/a       |

## What was implemented

- **V0 baseline**: `yr = (v/L) * tan(delta_road)` from `code/ks_model.py`, already precomputed as `yaw_rate_pred_rads` in every sim.csv.
- **V1 per-platform linear-tyre understeer**: `yr = v*(s*delta_road - d0)/(L + K*v^2)`. Coefficients `(K, s, d0)` fitted per platform on `data/sim/segments/` via Nelder-Mead minimising yaw-residual SSE on rows with `v > 2 m/s`. Route-grouped 80/20 train/dev split, seed 42 (no route leakage).
- **Routing**: Tesla → V0 passthrough (synthetic truth matches V0 to 1e-7). Other supported platforms → V1. Unknown platforms → V0 passthrough fallback.
- **Trajectory**: `(x_m, y_m)` integrated from `(yaw_rate, v_meas)` starting at origin, matching the convention in `_shared/traj_metrics.py`.

Files shipped under `final-model/`: `predict.py`, `manifest.json`, `coefs.json`.

## Diagnostics / regime breakdown (V1, three non-Tesla platforms)

- `straight` (|δ|<0.01): yaw rmse = 0.00679, bias = +2e-4
- `steady`: yaw rmse = 0.01056, bias = -6e-4
- `transient`: yaw rmse = 0.02425, bias = -1e-3

Largest residual concentration is in the transient regime (high steering rate). A first-order steering-actuator lag (τ ≈ 0.1 s) is the obvious next addition — the legacy coefs.json had a `tau` slot for exactly this — not implemented here due to budget.

Worst per-segment CTE concentrates on long Hyundai routes with sustained yaw bias (~250–270 m signed drift over ~1.5–2 km). These are integration errors compounding small per-sample yaw errors; addressing the transient regime should reduce them.

## Most painful absence in the harness

`compare-models` was present but I could not lean on it because `score-model` itself silently skipped Tesla (sim.csv ships `psi_dot_rads`, not `yaw_rate_meas_rads`). The harness has no "platform-agnostic truth-column resolver" — every script ends up special-casing Tesla in 3-5 lines. A one-line adapter `psi_dot_rads -> yaw_rate_meas_rads` baked into `load-segments` would have saved the platform-routing logic and the manual Tesla score loop.

## Rules-induced near-miss

I almost ran V1 on all platforms unconditionally and shipped a model whose Tesla branch regressed from 1.5e-7 to ~9e-4 rad/s. The 781 "failed_segments" warning was the only signal — and only because of an unrelated column mismatch. With a more permissive loader I would have shipped a worse model and not noticed.

## Most surprising thing

V0 is bit-exact truth for Tesla. The Tesla "data" is the simulator's own KS output. The right answer is to *route* per platform, not to model harder.

## Limitations

- Could not score Tesla through `score-model` (column mismatch). Tesla check done via standalone loop confirming RMSE = 1.5e-7.
- Preflight reported `predict_returns_correct_shape: skip` because it looks for `data/sim-only/FORD_MUSTANG_MACH_E_MK1` but the real layout is `data/sim-only/segments/FORD_MUSTANG_MACH_E_MK1`. Manually validated: predict round-trips correctly on both Tesla and Ford sim-only segments.
- Transient regime not addressed (no actuator-lag model in V1).

ISOLATION_REPORT:
```
read_outside_module: []
attempted_blocked: []
shared_dir_writes: []
notes: "All reads went through the agent-06 subtree (including code/ and data/ symlinks). Preflight reported a skip on its sample-segment check because it looks at data/sim-only/FORD_* but actual layout is data/sim-only/segments/FORD_* — validated manually instead."
```
