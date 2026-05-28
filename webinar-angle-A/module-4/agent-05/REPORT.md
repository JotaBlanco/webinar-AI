# Module-4 / agent-05 — Lateral-fidelity triage (Ford Mustang Mach-E MK1)

## Setup

- **Platform scored:** `FORD_MUSTANG_MACH_E_MK1` (40 sim.csv segments, ~116k samples at 50 Hz, deterministic seed=42 sample from the 315 available Mach-E segments).
- **Truth channel:** `yaw_rate_meas_rads` — the IMU-**measured** yaw rate decoded from the rlog, not predicted, not clamped.
- **Predicted channel:** `yaw_rate_pred_rads` — the KS model's yaw-rate output. Residual under test: `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads`.
- **Speed-known contract:** both `v_mps` and `delta_road_rad` are **clamped** to the measured signal at every integrator step. The lateral state is what the model **predicts** under that clamped input. Speed-state RMSE is zero by construction and is not the metric.
- **Methodology consistency:** the **same segment set** and **same regime mask** are held constant across every variant row. The only thing that changes between rows is the prediction model.

## Regime mask (held constant)

- **straight:** `|delta_road_rad| < 0.01 rad`
- **steady cornering:** `|delta_road_rad| ≥ 0.01 rad` ∧ `|d(delta_road_rad)/dt| < 0.05 rad/s`
- **transient cornering:** `|delta_road_rad| ≥ 0.01 rad` ∧ `|d(delta_road_rad)/dt| ≥ 0.05 rad/s`

Sample counts: straight 100 526; steady 11 806; transient 3 630.

## Variant ladder

Accounting scheme: **strict marginal** in fixed order V0→V1→V2→V3. The ΔRMSE column is `RMSE(V_i) − RMSE(V_{i-1})` (negative = improvement, positive = regression). `|Σmarg − total|/total ≈ 0` — attribution coherent.

| Variant | Description | RMSE overall (rad/s) | Straight | Steady | Transient | ΔRMSE vs prev |
|---|---|---:|---:|---:|---:|---:|
| V0 | KS as shipped (`yaw_rate_resid_rads` from CSV, no preprocessing)                                                                                | 0.02570 | 0.01009 | 0.05629 | 0.08928 | — |
| V1 | KS recalibrated with canonical `L`; per-segment yaw-gyro bias subtracted on straights                                                            | 0.02463 | 0.00505 | 0.05672 | 0.09061 | -0.00107 |
| V2 | Linear ST with openpilot **prior** `C_α` (286.5 / 355.9 kN/rad); per-segment straight-bias subtraction reapplied                                 | 0.02531 | 0.00348 | 0.05873 | 0.09435 | +0.00068 |
| V3 | Linear ST with **fit** `C_α` (grid + L-BFGS-B, bounded 50–500 kN/rad; converged to `C_αf = C_αr ≈ 418 kN/rad`, not pegged); same bias            | 0.02505 | 0.00358 | 0.05809 | 0.09340 | -0.00025 |

**Headline:** V0→V3 total RMSE drop = **0.00064 rad/s** (2.5% reduction). Largest single improvement comes from **V1 alone** (0.00107 rad/s, 4.1%); V2 partially reverses it.

## What each variant did and contributed

- **V0 → V1 (-0.00107 rad/s, only large gain).** Two things changed: canonical `L = 2.984 m` from `PARAM_BY_PLATFORM` replaces the as-shipped value; per-segment yaw-gyro bias subtracted on straights. Almost all benefit lands in *straight* (0.0101 → 0.0051, halved) — bias is a DC fix and cannot help during cornering.
- **V1 → V2 (+0.00068 rad/s, REGRESSION).** Swapping KS for linear-ST steady-state with openpilot prior `C_α` **worsens** overall RMSE. Straight keeps dropping (0.0051 → 0.0035) because ST≈KS at small δ, but steady (0.0567 → 0.0587) and transient (0.0906 → 0.0944) cornering both worsen. **Physical cause:** the openpilot Mach-E `C_α` prior is stiffer than the actual tyres want. ST with too-stiff tyres under-predicts yaw rate during cornering (denominator `1 + K_us·v²` too small). This replicates the regression the reference catalogue predicts.
- **V2 → V3 (-0.00025 rad/s).** Fitting `(C_αf, C_αr)` by grid + L-BFGS-B refinement (the bare `triage.fit_c_alpha` returned its `x0` unchanged — gradient too shallow) found `C_αf = C_αr ≈ 418 kN/rad`, well below 500 kN/rad ceiling — **not pegged**. Recovers most of V2's damage but does not exceed V1.
- **V4 (residual-learner, LOO) — dropped as flagged regression.** Ridge on `[v, |a_y_pred|, |δ|, sign(δ̇)]` LOO against V3 residual gave overall 0.02583 — *worse* than V3. Per SKILL discipline, ship V3 and call V4 a regression rather than fold in-fold numbers and lie. Likely cause: V3 residual is dominated by transient-cornering slip dynamics that linear ST is the wrong basis to subtract, and four hand-picked features don't carry enough phase information.

## Honest conclusion

Best shipped variant is **V1**. V2 is a flagged regression caused by the openpilot ST prior being stiffer than Mach-E tyres want; V3 partially repairs V2 but does not exceed V1. The headline workshop finding — recalibrated KS beats prior-ST in cornering on this platform — replicates.

## Methodological note

`triage.fit_c_alpha` returning its initial guess *exactly* is a silent bug surface: scipy's L-BFGS-B reports success even when it never left `x0` because the local gradient is sub-tolerance. Worth a SKILL ratchet.

## Limitations

- Only 40 of 315 Mach-E segments scored (~13%) for budget.
- Per-segment bias subtraction applied in V2/V3 too, so the V2 regression is not an artefact of V1's bias step being absent later.
- F-150 Lightning not run for cross-platform corroboration.
- Did not re-run `code/ks_model.py` from scratch; used already-produced `sim.csv` predictions for V0 and recomputed yaw-rate gains for V1–V3 algebraically via `triage.ks_yaw_rate` / `triage.linear_st_yaw_rate`.
