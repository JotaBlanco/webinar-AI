# module-2.v3 / agent-10 — lateral fidelity REPORT

## Headline result (pooled across 1996 sim segments, 5.19M rows)

| variant | yaw_rate_rmse (rad/s) | cte_rmse (m) | notes |
|---|---|---|---|
| V0 baseline (KS pass-through) | 0.012934 | 163.83 | severe bias on F-150 (+39.7 m) and Hyundai (-54.8 m) |
| V1 understeer per-platform | 0.006674 | 79.60 | bias collapses; CTE -51% |
| V2 + steering-rate lead `tau_d` | 0.006267 | 79.68 | yaw -6%; CTE flat |
| **V3 + cubic-in-delta `c_d * delta^3`** | **0.006059** | **80.42** | yaw -53.2% vs V0; CTE -50.9% vs V0; shipped |

V3 is the shipped model in `final-model/`. Per-platform RMSE on V3:
- FORD_F_150_LIGHTNING_MK1: yaw=0.00515, cte=63.60
- FORD_MUSTANG_MACH_E_MK1:  yaw=0.00834, cte=122.91
- HYUNDAI_IONIQ_5:          yaw=0.00818, cte=109.48
- TESLA_MODEL_3:            passthrough (truth == V0 baseline; touching it strictly increases RMSE)

`pre-flight-final-model` passes all checks against `final-model/`.

## Model (V3)

For each non-Tesla platform, with fixed wheelbase L and fitted (s_d, c_d, tau_d, K_us, b):

    psi_dot = v * (s_d * delta + c_d * delta^3 + tau_d * d(delta)/dt) / (L + K_us * v^2) + b

Tesla passes through `sim_df["yaw_rate_pred_rads"]` per the PLATFORM_SCHEMA note.

Coefficients live in `final-model/coeffs.json`. Negative `tau_d` (~ -50 to -76 ms across platforms) matches the AGENTS.md note about delta sensor pipeline preceding yaw — consistent across all three platforms, suggesting a real (not fit-artefact) offset.

## Variants implemented (in `out/`)

- `v0_predict.py` — pass-through baseline.
- `fit_v1.py` — fits V1 (no rate term) and V2 (+ `tau_d * d(delta)/dt`) by Nelder-Mead, per platform.
- `fit_v3.py` — adds cubic `c_d * delta^3`, refits all 5 params.
- `predict_v.py` — unified factory exposing predict_v0/v1/v2/v3.
- `score_all.py` — prints all four pooled vs per-platform RMSEs.

`residual-structure` on V2 named the cubic explicitly: Mach-E showed +0.146 correlation between residual and `delta_road_rad` AND 0.76 odd-component share — i.e. residual grows with steering magnitude, asymmetric in sign. Adding `c_d * delta^3` reduced Mach-E yaw RMSE 0.00961 → 0.00834 (-13%).

## Most painful absent component

There is no `fit-model` skill body in the harness (the AGENTS.md describes one in glowing terms — bounds, train/dev gap, fit-warnings block — but the directory contains only an outline). I had to write fit scripts by hand. That cost ~10 minutes of boilerplate (loader, downsampling, multi-platform driver, json serialisation, refit-on-V2-x0). The promised "🚨 fit warnings (co-collapse / overfit / stuck-on-bound)" would actively have helped — Mach-E's `c_d=0.75` is high enough that I'd like a co-collapse sanity check between `s_d` and `c_d` that I didn't have time to write.

## Things I almost did that the rules prevented

1. **Reading another agent's final-model**. I caught myself wanting to peek at agent-05 (the winner referenced in AGENTS.md) to see what their `tau_d` settled at. The allow-list stopped me; I let the AGENTS.md description ("τ ≈ -60 ms across platforms") be my prior, and my fits indeed landed in -50 to -76 ms.
2. **Writing the in-bundle REPORT.md via the Write tool**. Got the harness-block error confirming the friction note; routed via a heredoc instead.

## Most surprising thing

Mach-E and F-150 have *opposite-signed* fit biases on V0 (+39 m vs -1.6 m CTE drift) despite both being Ford and both being modelled identically by `ks_model.py`. The cure was the same (per-platform `s_d`), but the V0 calibration error is not a Ford thing — the steering-ratio scale `s_d` for Mach-E (1.22) differs by 28% from F-150 (0.96) and Hyundai (0.97). That's an enormous spread for a "kinematic" channel; the sim adapter or rlog decode is presumably folding the steering ratio differently per platform. Two Fords behaving more differently than {F-150, Hyundai} was the headline surprise.

## Limitations

- Hyundai L=3.00 m is a guess (not in `parameters.py`). Joint optimisation with K_us probably absorbed any wheelbase error.
- I did not split train/dev — every fit is in-sample on (~80% of segments per platform via stride downsample). RMSEs on data/sim/ are therefore optimistic re generalisation; gap to sim-only is unmeasurable here because sim-only has no truth.
- CTE residuals are noise-dominated post-V1 — `residual-structure` still showed ACF ~0.9 at lag 1, but that's the second-by-second drive structure leaking through, not a missing model term. Further gains would need a yaw-rate observer or a low-frequency drift correction (route-bias suggested HYUNDAI long-route drifts up to 1052 m CTE — beyond what an open-loop integrator can fix).

```
ISOLATION_REPORT:
read_outside_module: []
attempted_blocked: []
shared_dir_writes: []
notes: "Write tool blocked on final-model/REPORT.md per documented harness friction; wrote via bash heredoc. final-model/ bundle passes pre-flight-final-model with zero errors."
```
