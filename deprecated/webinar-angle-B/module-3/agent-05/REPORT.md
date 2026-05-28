# Module-3 / agent-05 (angle-B) — Lateral fidelity ladder

**Platform:** `FORD_MUSTANG_MACH_E_MK1` (Ford required for lateral truth; Tesla has no yaw-rate measurement). 306 segments, 810 208 samples at 50 Hz after `v ≥ 2 m/s` gate.

**Clamped vs predicted:** `v` and `δ_road` are clamped to measurement (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Predicted channel under test is `yaw_rate_pred_rads`. Metric is RMSE of `yaw_rate_pred − yaw_rate_meas_rads`. Sign sanity: `corr(δ_road, ψ̇_meas)` on cornering = **+0.922** (correct).

## Variant ladder (cumulative, same segment set, same regime mask)

| Variant | Description | RMSE all | straight | steady | transient | Marginal drop |
|---|---|---:|---:|---:|---:|---:|
| V0 | KS baseline (CSV as-is) | 0.01316 | 0.00912 | 0.02438 | 0.04362 | — |
| V1 | V0 + per-segment straight-line bias (IMU gyro offset) | **0.01105** | 0.00511 | 0.02401 | 0.04404 | **-0.00211** |
| V2 | Linear ST, prior C_α (openpilot) + per-seg bias | 0.01225 | 0.00348 | 0.02855 | 0.05213 | +0.00121 (regression) |
| V3 | Linear ST, fit C_α (bounded 50–500 kN/rad) + per-seg bias | 0.01166 | 0.00365 | 0.02663 | 0.04996 | -0.00059 |

Total drop V0→V3 = -0.00150 rad/s (≈11% of V0). Sum of marginals = -0.00150 — exact, no double-counting. Accounting scheme: **last-rung-wins** (each marginal is `RMSE(V_{n−1}) − RMSE(V_n)` on the full all-regime pool).

## Findings, named

- **Painful absence — slip.** KS has no tyre slip. Cornering residual (steady 0.024, transient 0.044 rad/s) is what an ST/Pacejka rung *could* close. The ST upgrade here doesn't, because the openpilot prior C_α is calibrated for very sticky OE rubber and the residual structure suggests less stiff effective tyres on this test data.
- **The win that mattered — IMU bias.** V1 alone removed 16% of V0 RMSE, almost entirely from the straight regime (0.00912 → 0.00511). Per-segment yaw-gyro offset masquerading as model error. One DOF per segment, free improvement.
- **Near-miss — fit C_α.** V3 lands at C_αf ≈ C_αr ≈ 400 kN/rad (interior, **not** pegged at the 500 kN/rad bound). It claws back ~half of V2's cornering regression but never beats V1. The linear-ST form is the wrong shape, not just wrong-prior.

## Honest regression flags

- V2 regresses against V1 on every cornering regime (steady +19%, transient +18%). The prior stiffnesses make steady-state yaw gain too large at the speeds in this fleet.
- C_α fit is **not pegged** at the upper bound, but symmetric front=rear=400 kN/rad beating both the asymmetric prior and physical front/rear split is a soft red flag of its own — likely tyres-saturating at moderate `|a_y|` that the linear form cannot capture.

## What I did not do

- No residual learner (out of scope — would need LOSO CV to be honest).
- No Pacejka — out of scope per skill notes.
- F-150 Lightning not scored to avoid mixing platforms in one ladder.

## Headline

**The biggest lateral-fidelity win was not a model upgrade — it was per-segment IMU yaw-gyro bias removal (-0.00211 rad/s, ~16% of V0). Climbing to linear ST with openpilot's production C_α priors *regresses* cornering RMSE by ~19%; refitting C_α partially recovers but never beats the bias-corrected KS. The linear-ST form, not just the priors, is the wrong rung for this data.**

Files: `tools/run_ladder.py`, `out/ladder_results.json`.
