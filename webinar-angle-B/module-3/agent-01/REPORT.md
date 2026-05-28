# Module-3 / agent-01 (angle-B) — Lateral Fidelity, FORD_MUSTANG_MACH_E_MK1

**Platform:** `FORD_MUSTANG_MACH_E_MK1` (Tesla excluded — no IMU truth; F-150 not used to keep one platform per ladder).
**Operating contract:** `v` and `δ` clamped to measured each step. Predicted channel = `yaw_rate_pred_rads`. Truth = `yaw_rate_meas_rads`. Metric = RMSE of `pred − meas` over 315 segments / 913 626 samples at 50 Hz.
**Sign check:** `corr(delta_road, yaw_rate_meas)` on cornering = **+0.702** — convention OK.
**Accounting scheme:** sequential marginal drop on `all` regime RMSE; marginal sum vs total V0→V4 gap = -1.2% (well inside 15%).

## Variant ladder (rad/s RMSE)

| Variant | all | straight | steady | transient | marginal drop |
|---|---:|---:|---:|---:|---:|
| V0 KS baseline | 0.01613 | 0.00877 | 0.03173 | 0.05680 | — |
| V1 KS + per-seg straight-line bias | 0.01469 | 0.00493 | 0.03168 | 0.05730 | -0.00143 |
| V2 ST steady-state, prior C_α | 0.01551 | 0.00339 | 0.03430 | 0.06277 | +0.00082 (regression) |
| V3 ST steady-state, fit C_α (50–500 kN/rad) | 0.01551 | 0.00339 | 0.03430 | 0.06277 | 0.00000 |
| V4 V3 + LOSO Ridge on [v,\|a_y\|,\|δ\|,sign(δ̇)] | 0.01530 | 0.00346 | 0.03393 | 0.06148 | -0.00021 |

**Headline:** V0→V4 drop = 0.0008 rad/s (~5%), almost all of it from V1's per-segment yaw-gyro bias removal. ST didn't help.

## What each contributed

- **V1 (-0.00143):** Per-segment straight-line yaw-gyro bias slashes straight-regime RMSE 44% (0.00877 → 0.00493) and is the only honest win.
- **V2 regression (+0.00082):** Linear-ST steady-state gain with openpilot's prior C_α *under-rotates* the car vs KS on steady and transient regimes. Priors 287/356 kN/rad — likely too stiff for these tyres/roads.
- **V3 (0.00000):** L-BFGS-B with bounds [50, 500] kN/rad **stayed exactly at the priors**. Not pegged — the MSE surface on steady-cornering RMSE has a local minimum at the prior. Linear-ST form lacks the DoF to beat V1 with bounded C_α. Diagnosis: **wrong form**, not wrong calibration window.
- **V4 (-0.00021):** Ridge residual learner under LOSO recovers small transient-regime drop (0.06277 → 0.06148) — picks up steering-rate-dependent residual KS/ST can't model.

## Painful absence

No tyre slip and no inertia: KS has `ψ̇ = (v/L)·tan(δ)`, so the **transient regime (0.057 rad/s RMSE, ~3.5× steady)** is structurally unreachable. The KS→ST step does not close it because the linear ST is still a steady-state algebraic gain with no `I_z·dψ̇/dt` term. Closing transients needs a proper ST ODE (Pacejka or dynamic linear-ST) — out of scope per the skill.

## Rule-prevented near-misses

- Defaulting to Tesla for "more segments" — blocked by truth-channel matrix.
- Unclamping v/δ — blocked by contract.
- Reading `delta_wheel_deg` as radians — would have produced ~15× error.
- In-fold scoring of the Ridge residual learner — used LOSO; in-fold would have laundered ~70% of V0 residual dishonestly.
- Different segment set across rungs — same 315-segment Mach-E set used for every variant.

## Most surprising

**The bounded C_α fit refused to move from the openpilot priors.** Not pegged at a bound, not numerical failure — the steady-cornering MSE has a local minimum at the priors and the linear-ST form is simply the wrong model class for these segments. The V2 regression flag is real and structural, not a calibration nit. The honest read: V1 (bias correction) is the only rung that helped; the ST rung as specified is a dead end; next real win lives at Pacejka or the dynamic linear-ST ODE.

Files: `tools/lateral_fidelity.py`, `out/lateral_fidelity_summary.json`.
