# REPORT — module-3-agent-04 (lateral fidelity, idea-01)

## TL;DR
This is a **retry run** that inspected and validated the artifact a previous session shipped before hitting its limit. The artifact is sound; no re-fit was required. Final scores against the full sim dataset (train+dev pooled, all 4 platforms):

| Metric | V0 | Final | Δ |
|---|---|---|---|
| Yaw-rate RMSE (rad/s) | 0.01293 | **0.00637** | **-50.7%** |
| CTE RMSE (m)          | 163.83  | **72.64**   | **-55.7%** |

Held-out dev (route-grouped, ~25% routes per platform, Tesla excluded): yaw **0.00820**, cte **99.87** — gap to train is modest, no overfit pathology.

Per-platform (pooled):

| Platform | yaw RMSE | CTE RMSE | signed yaw bias |
|---|---|---|---|
| FORD_F_150_LIGHTNING_MK1 | 0.00581 | 59.60  | +0.00027 |
| FORD_MUSTANG_MACH_E_MK1  | 0.00775 | 108.59 | -0.00085 |
| HYUNDAI_IONIQ_5          | 0.00884 | 99.48  | -0.00086 |
| TESLA_MODEL_3            | 0.00000 | 0.000  | +0.00000 (V0 passthrough — Tesla has no independent truth) |

## What was implemented
Single structural variant: **per-platform polynomial steering scale + understeer + first-order yaw lag**, fit per platform with L-BFGS-B in two stages (yaw-only, then yaw+CTE warm-start).

- Steady-state yaw: `yr_ss = v · δ_eff(δ - δ₀) / (L_eff + K_us · v²)` with `δ_eff = g0 + g2·δ²` (polynomial nonlinear gain).
- First-order lag: `yr[i] = yr[i-1] + (dt/(τ+dt)) · (yr_ss[i] - yr[i-1])`.
- Per-segment δ₀ for Mach-E & Ioniq, global δ₀ for Lightning (driven by which platform's bias-spread fell after per-segment δ₀ — Lightning's didn't).
- Straight detector for δ₀ uses `|v · yaw_rate_pred_rads| < 0.3 m/s²` (V0 baseline as a_lat proxy — `a_lat_meas_mps2` is **not** in the grading allowlist).
- Tesla: V0 passthrough. Scoring Tesla against truth is meaningless because Tesla's "truth" channel `psi_dot_rads` IS the V0 output.
- Trajectory: trapezoidal integration of predicted yaw with measured v.

## Validation
- `skills/pre-flight-final-model` passes 8/9 checks (only REPORT.md missing, which orchestrator persists).
- Predict round-trips one `sim-only/` segment per platform with no `KeyError` and no truth-column dependency.
- Score-model output reproducible from `out/fit_summary.json`.

## Most painful absent component
**No `compare-trajectories-on-route` skill** — given two predict()s and a segment, render the *integrated trajectories* on top of truth in x-y space and bin CTE by curvature / speed / time-since-turn-start. Numerically I have CTE RMSE, but with V0 → final dropping 55%, I couldn't quickly see *where* the remaining 72m comes from: long-radius drift, accumulated heading bias, or transient-corner overshoots. `inspect-residuals/` only does yaw vs feature; I'd have had to write the trajectory-overlay tool myself, and chose not to spend the budget on it.

## What the rules prevented me from almost doing
Twice I caught myself wanting to peek at parallel `agent-0X/` directories to see what structural rungs other runs were trying (especially whether anyone went past polynomial-gain to a linear dynamic single-track with slip angles, which `references/dynamics-formulations.md` sketches but doesn't implement). Isolation rules blocked that — and that's the workshop point: this run is a single substrate's verdict on a single rung, not a peeking-aggregated answer.

## Most surprising thing
The polynomial term **`g2`** went **negative** for Hyundai Ioniq 5 (-0.023) but strongly positive for the two Fords (Lightning +0.32, Mach-E +0.79). For all three I'd assumed the steering compliance/nonlinearity would have the same sign — softer at small angles, stiffer near the rack-end. The Ioniq fit says the opposite, and the fit was healthy (yaw bias only -0.0009 rad/s). Either the Ioniq has unusual steering ratio behaviour, or `g2` is absorbing some other unmodeled effect (tyre cornering stiffness drop with load?). With ceiling-moves available this would be the lever to pull next.

## Files of interest (all absolute)
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-04/final-model/predict.py`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-04/final-model/coeffs.json`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-04/final-model/manifest.json`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-04/out/fit_summary.json`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-04/out/fit_models.py`
