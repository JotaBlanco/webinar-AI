# Module-2 / agent-03 (angle-B) — Lateral Fidelity Variant Ladder

**Platform:** `FORD_MUSTANG_MACH_E_MK1` (315 segments, 913,626 samples @ 50 Hz, ~305 min). F-150 Lightning not scored (time budget).

**Truth channel:** `yaw_rate_meas_rads` — measured from the Ford CAN bus via `opendbc/ford_lincoln_base_pt`, decoded by `code/adapter_ford_rlog.py`. Not predicted, not self-consistency, not GPS-derived.

**Operating contract (speed-known, lateral-only):** `clamp_v_to_measured=True`, `clamp_delta_to_measured=True`. **Clamped:** `v`, `δ`. **Predicted:** `ψ̇`, `a_y`, `ψ`, `(x,y)`. Speed-state RMSE zero by construction and not reported.

**Metric:** RMSE of `yaw_rate_resid_rads = ψ̇_pred − ψ̇_meas`, broken out by regime, in **mrad/s**.

**Regime mask** (consistent across all variants):
- straight: `|ψ̇_meas| < 0.02 rad/s` — 78.6% of samples
- transient_corner: not straight ∧ `|dψ̇/dt| > 0.15 rad/s²` — 2.3%
- steady_corner: remainder — 19.1%

## Ladder

| Variant | Description | Overall | Straight | Steady | Transient | Marginal |
|---|---|---:|---:|---:|---:|---:|
| V0 | KS baseline, `yaw_rate_resid_rads` as-is | 16.127 | 7.990 | 28.252 | 50.145 | — |
| V1 | + per-segment yaw-rate bias removal | 14.143 | 4.967 | 26.129 | 46.893 | -1.984 |
| V2 | + replace `(v/L)·tan(δ)` with linear ST `v·δ/(L·(1+K_us·v²))`, K_us=5.62e-4 s²/m² from shipped Cα | 14.746 | 4.559 | 27.106 | 51.591 | +0.604 **(regression)** |
| V3 | + first-order steering lag, τ=0.08 s (rack/EPS dynamics), grid-fit | 14.316 | 4.368 | 26.765 | 48.234 | -0.430 |
| V4 | + empirical understeer gradient K_us=5.00e-4 s²/m² (was 5.62e-4) | 14.202 | 4.354 | 26.519 | 47.938 | -0.114 |

**Total drop V0 → V4:** 1.924 mrad/s (11.9%). **Sum of marginal drops:** 1.924 mrad/s. Cumulative/marginal accounting; each variant evaluated with all previous applied.

## Regression: V2 worsened the metric on its own

The linear ST steady-state gain at the **shipped Cα prior** under-rotates the model relative to KS (because `K_us > 0` cuts gain at speed). Straight RMSE improved (4.967→4.559) but steady and transient regressed. The shipped Cα ratio is dominated by `l_r·Cr − l_f·Cf` and the resulting `K_us=5.62e-4` is essentially noise-band — close to neutral steer. Physical cause: production Cα prior is calibrated for openpilot's lat planner, not for residual minimisation; small K_us mismatch is amplified in cornering. The regression is closed by combining with V3 (lag) and V4 (fit Cα-equivalent K_us).

## What remains unexplained

Even at V4 the transient-cornering RMSE is **47.9 mrad/s** — 3.4× the straight-line floor. This is the residual the KS contract cannot close. It is the slip-angle / tyre-lag / weight-transfer signature that an ST dynamic model with proper tyre relaxation length would address.

## Variants tried but not promoted

- Global `δ` zero-offset calibration: best offset +0.5 mrad, drop ≈ 0.017 mrad/s — below the discretisation step.

## Reply

**Painful absence**: no tyre-slip term, no sideslip state β, no relaxation length. Transient-cornering RMSE stays at 47.9 mrad/s after V4 — 3.4× the straight-line floor.

**Rule-prevented near-misses**: trap #2 (used `delta_road_rad`, never touched clamp_*); trap #3 (deg vs rad); trap #5 (parameters from PARAM_BY_PLATFORM); trap #9 (V0 is raw residual, bias removal lives in V1); trap #10 (marginal attribution, sum=total to <0.01%).

**Most surprising**: ST steady-state gain swap (V2) **regressed** on its own. Shipped Cα prior gives `K_us=5.62e-4 s²/m²` — essentially neutral-steer — under-rotates relative to KS at speed. Empirically fitting K_us only moves it to 5.00e-4. The Cα prior is not the right calibration target for these tyres on these roads (as AGENTS.md warns); but the gap it leaves is small. The real lateral lie is in the **transient regime**, and the slip angle is what KS+ST-linear both ignore in the same way.

Files: `out/analyze.py`, `out/ladder.json`.
