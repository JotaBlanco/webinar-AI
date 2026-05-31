# agent-04 — lateral-fidelity final model

## TL;DR

Per-platform closed-form bicycle model with **polynomial steering scale**, steering offset, speed-dependent understeer, and first-order yaw-rate lag. Tesla = V0 passthrough. Fitted on whole-route train split, evaluated on held-out dev.

| KPI | V0 baseline | Final (V2) | Improvement |
|---|---|---|---|
| Yaw-rate RMSE (full data, rad/s) | 0.01479 | **0.00726** | **−51%** |
| CTE RMSE (full data, m) | 152.00 | **101.53** | **−33%** |
| Yaw-rate RMSE (dev) | 0.01575 | **0.00687** | −56% |
| CTE RMSE (dev) | 159.20 | **79.49** | −50% |

Per platform (full data):

| Platform | yaw V0 → V2 | CTE V0 → V2 |
|---|---|---|
| FORD_F_150_LIGHTNING_MK1 | 0.0163 → **0.0053** (−68%) | 157.5 → **61.3** (−61%) |
| FORD_MUSTANG_MACH_E_MK1 | 0.0136 → **0.0084** (−39%) | 148.0 → **122.1** (−18%) |

## Model

For each FORD platform we compute the steady-state yaw rate from a closed-form single-track bicycle augmented with three corrections, then pass it through a first-order yaw-rate lag.

```
g_eff(δ)  = g0 + g1 · |δ|                         # polynomial steering scale
yr_ss(t)  = v(t) · g_eff(δ) · (δ(t) − δ0) / (L + K_us · v(t)²)
yr_pred[k] = (1 − α[k]) · yr_pred[k−1] + α[k] · yr_ss[k],    α[k] = dt[k]/(τ + dt[k])
```

Five fitted parameters per platform: `g0, g1, δ0, K_us, τ`.

Trajectory `(x_m, y_m)` is integrated from `(yr_pred, v_meas)` using the same Euler scheme as the canonical CTE metric (zero-order hold, start at origin).

## Why these terms

| Term | Why it's there |
|---|---|
| `g0` | Linear steering scale — base actuator/ratio bias. |
| `g1 · |δ|` | **Captures the nonlinearity in the Mach-E steering rack** that the linear-g V1 couldn't. Mach-E fits g1≈0.52; Lightning g1≈0.24. Most of the V2-over-V1 CTE win on Mach-E (159→87 on dev) comes from this. |
| `δ0` | Small steering offset removes the constant yaw-rate bias that integrates into trajectory drift. |
| `K_us · v²` | Speed-dependent understeer — standard bicycle term. |
| `τ` | First-order yaw-rate lag — vehicle-dynamic delay between steering input and yaw response (~60–70 ms here, consistent with priors). |

## Fitted coefficients

```json
{
  "FORD_F_150_LIGHTNING_MK1": {
    "g0": 0.9030, "g1": 0.2447, "delta0": 0.00115,
    "K_us": 0.00289, "tau": 0.0624, "L": 3.70
  },
  "FORD_MUSTANG_MACH_E_MK1": {
    "g0": 1.1003, "g1": 0.5165, "delta0": -0.00010,
    "K_us": 0.00211, "tau": 0.0680, "L": 2.984
  }
}
```

Lightning has lower steering scale (`g0 < 1`) and higher `K_us` (heavier, longer wheelbase). Mach-E has stronger steering nonlinearity (`g1` 2× Lightning's). Neither fit pegs a bound.

## Fitting protocol

- **Split**: stratify by platform; whole-route holdout (group by `(device, route)`), 25% dev fraction, seed 42 — using the toolkit `make-train-dev-split` skill (matches the `anti-patterns.md` guidance against sample-level leakage).
- **Loss**: per-platform sample-pooled yaw-rate MSE for `v > 2.0 m/s` (matches the score-model filter).
- **Optimizer**: Nelder-Mead with 4–5 starting points, picking the best minimum.
- **Bounds**: soft penalty for out-of-range parameters; none of the fits land on a bound.

A CTE-aware loss was attempted but evaluation cost (trajectory integration per call) made the Nelder-Mead descent infeasible in budget. Pure yaw-MSE was enough to win both KPIs.

## Tesla

`TESLA_MODEL_3` has no `yaw_rate_meas_rads` truth channel. Per `anti-patterns.md`, fitting blind would not move the score; we fall back to V0 passthrough.

## Per-regime breakdown (dev)

| Regime | n samples | yaw RMSE |
|---|---|---|
| straight | 228 105 | 0.00582 |
| steady cornering | 30 215 | 0.00997 |
| transient | 7 720 | 0.01535 |

Residual is concentrated in the transient regime. An obvious next move (per `approach-menu.md`) is the dynamic single-track with slip angles or a higher-order steering filter to capture transient overshoot.

## What I tried and dropped

- **V1 (linear g, no polynomial)**: halved yaw RMSE but *worsened* Mach-E CTE (141 → 159). Classic "wins yaw, loses CTE" — a systematic bias the linear scale couldn't absorb. The two-KPI tradeoff doc named the pattern; the polynomial-g fix followed directly.
- **CTE-aware loss** (yaw MSE + λ · CTE MSE): too slow inside Nelder-Mead at 150-segment scale to finish in budget. Worth revisiting with a JIT'd integrator.

## What would close the remaining gap

- **`a_lat_meas_mps2` fusion** — a complementary filter on `a_lat/v` vs the model output. Listed as unexplored in the approach menu and would attack the Mach-E CTE residual where it's still ~2× Lightning.
- **Dynamic single-track with slip angles** — for the transient-regime residual.
- **Speed-dependent understeer** `K_us(v)` — small-effect but cheap.

## Files

- `predict.py` — `predict(sim_df, platform) -> DataFrame[yaw_rate_pred_rads, x_m, y_m]`.
- `coeffs.json` — fitted parameters per platform.
- `manifest.json` — platform support + predict callable hook for the grader.

## Pre-flight

All grader checks pass except `report_md_present` (harness blocks REPORT.md writes from sub-agents; parent assistant persists this content).
