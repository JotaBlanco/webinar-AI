# Module 3 — Lateral-fidelity submission (agent-07)

## Model

Per-platform kinematic single-track with understeer and first-order yaw lag:

```
yr_ss(t) = g · (δ(t) − δ₀) · v(t) / (L + K_us · v(t)²)
yr(t)    = lowpass( yr_ss(·), τ )      # variable-dt first-order
```

`(x, y)` are integrated with the same zero-order-hold Euler scheme the grader uses (`_shared/traj_metrics.integrate_trajectory`). Tesla has no measured yaw-rate channel; for Tesla we fall back to V0 passthrough (`yr = (v/L)·tan δ`).

## Fitted coefficients

| Platform | L (m) | g | δ₀ (rad) | K_us | τ (s) |
|---|---|---|---|---|---|
| Ford Mustang Mach-E MK1 | 2.984 | 1.1762 | 1.01e-4 | 0.002638 | 0.0684 |
| Ford F-150 Lightning MK1 | 3.70 | 0.9813 | 1.19e-3 | 0.004144 | 0.0613 |
| Tesla Model 3 | 2.875 | — (V0 passthrough) | — | — | — |

Notes on the numbers:
- Mach-E `g ≈ 1.18` means the carParams steering ratio is ~18% optically too low for what the road actually does; Lightning `g ≈ 0.98` is essentially unity. Different platforms, different stories — exactly the anti-pattern warning.
- Lightning's `K_us` is 1.6× Mach-E's, matching the heavier vehicle / longer wheelbase / stronger understeer described in the references.
- `τ ≈ 60–70 ms` is right in the range the approach-menu predicted for first-order yaw lag.
- δ₀ is small but matters for CTE — a constant 1 mrad offset integrates to metres of drift on a long segment.

## Fitting procedure

- Route-level train/dev split (25% dev), seeded with `rng=42`. Routes identified by `(device_id, route_id)`; no route bleeds across the boundary.
- Per platform, fit on a random 40-segment subset of train (CPU-bounded, full-train would have been overkill).
- Loss: mean-squared yaw-rate residual over samples with `v_mps > 2.0`.
- Optimiser: SciPy Nelder-Mead, initial point `g=1, δ₀=0, K_us=0.002, τ=0.07`. V2 starts from the V1 optimum.

## Variants tried

| Variant | Description | Dev yaw RMSE Mach-E / Lightning | Verdict |
|---|---|---|---|
| V0 | `(v/L)·tan(δ)` | 0.01467 / 0.01288 | baseline |
| V1 | KS + g, δ₀, K_us | 0.01096 / 0.00506 | strong gain |
| V2 (shipped) | V1 + first-order lag τ | 0.01029 / 0.00465 | +5–10% on V1 |
| V3 | V2 + α·(a_lat/v) blend | 0.01033 / 0.00465 | α optimised to ≈0; dropped |

## Headline numbers — full Ford eval set

| | yaw RMSE (rad/s) | CTE RMSE (m) |
|---|---|---|
| V0 overall | 0.01479 | 152.0 |
| Final overall | **0.00785** (-47%) | **103.6** (-32%) |
| V0 Mach-E | 0.01362 | 148.0 |
| Final Mach-E | 0.00907 (-33%) | 124.2 (-16%) |
| V0 Lightning | 0.01633 | 157.5 |
| Final Lightning | 0.00566 (-65%) | 63.9 (-59%) |

Per-regime yaw RMSE for the shipped model: straight 0.0063, steady 0.0118, transient 0.0181 — transient dominates the residual, consistent with the references' guidance.

## Reading the two KPIs

Yaw RMSE drops 47%, CTE drops 32% — yaw improvement noticeably outruns CTE improvement. By the `two-kpi-tradeoff.md` table that's the "residual systematic bias" pattern. The platform split shows it concentrates on Mach-E (CTE only -16%); Lightning is symmetric (-65%/-59%, a clean win on both). Most plausible source for the Mach-E gap: steering nonlinearity that a single scalar `g` cannot absorb — a polynomial `g(δ) = g₀ + g₂·δ²` is the natural next step (approach-menu calls it `[unexplored]`). Not pursued due to time budget.

## Pre-flight

All `pre-flight-final-model/preflight.py` checks pass except `report_md_present` — that's the file you are reading, persisted by the parent agent because writing files matching the `report` pattern is blocked in the sub-agent harness.

## What I did not do

- No `a_lat` complementary fusion in the shipped model (V3 fit returned α≈0 — the lag-corrected physics already captures what the lateral-accel channel would add at this fidelity).
- No polynomial steering scale `g(δ)`. This is the single most likely lever for the remaining Mach-E CTE gap.
- No Pacejka / dynamic single-track. Most segments are below tyre saturation, expected gain small per the references.
- No fit on Tesla — no truth channel, V0 passthrough by design.
