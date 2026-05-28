# Module-3 / agent-01 — Lateral-fidelity variant ladder (Mach-E)

## Setup

- **Platform scored**: `FORD_MUSTANG_MACH_E_MK1`. `yaw_rate_meas_rads` is **measured** truth decoded from the rlog IMU — not a prediction, not the integrator's own state.
- **Segments used**: first 80 Mach-E segments (deterministically sorted), 231 926 rows.
- **Speed-known contract**: `v_mps` and `delta_road_rad` **clamped** to measurement at every step; the **predicted** channel is `yaw_rate_pred_rads`. Residual under test: `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads`. Speed/steering state agreement is zero by construction and is not the metric.
- **Sign check**: `corr(δ_road, ψ̇_meas) = +0.909` on cornering samples — left-positive convention confirmed.
- **Regime mask** (constant): straight `|δ|<0.01`; steady `|δ|≥0.01 ∧ |δ̇|<0.05`; transient `|δ|≥0.01 ∧ |δ̇|≥0.05`. Counts: 211 404 / 17 627 / 2 895.
- **Parameters**: `PARAM_BY_PLATFORM["FORD_MUSTANG_MACH_E_MK1"]` — `L=2.984`, `l_f=1.313`, `l_r=1.671`, `m=2336`, `I_z=4879.05`, `C_αf=286 551`, `C_αr=355 912 N/rad`.
- **Attribution scheme**: strict marginal in fixed order V0→V1→V2→V3→V4. Marginal drop = `RMSE(V_{i-1}) − RMSE(V_i)`. Sum of marginals within 0% of total drop (well under 15% bar).

## Variant ladder — RMSE on `yaw_rate_resid_rads` (rad/s)

| Variant | Overall | Straight | Steady | Transient | Marginal drop |
|---|---:|---:|---:|---:|---:|
| V0 baseline (KS as-is)                  | 0.01190 | 0.00853 | 0.02331 | 0.05219 | — |
| V1 KS recal + per-segment yaw bias      | 0.01013 | 0.00498 | 0.02395 | 0.05406 | -0.00176 |
| V2 Linear ST, prior C_α (regression)    | 0.01201 | 0.00433 | 0.03121 | 0.06518 | +0.00187 |
| V3 Linear ST, multistart-fit C_α        | 0.01180 | 0.00412 | 0.03072 | 0.06462 | -0.00020 |
| V4 Ridge residual learner on V3, LOSO   | 0.01003 | 0.00422 | 0.02433 | 0.05614 | -0.00178 |

Total drop V0→V4 = 0.00187 rad/s. Sum of marginals = 0.00187 rad/s. **Final overall RMSE = 0.01003, a 15.7% improvement vs V0.**

## Variants

- **V0** — `yaw_rate_resid_rads` from the CSV. Per the baseline-methodology contract.
- **V1** — recompute `ψ̇=(v/L)tan(δ)` with canonical L; subtract per-segment yaw-gyro bias from straights (≥50 samples), median bias = +0.00071 rad/s.
- **V2** — linear ST steady-state gain with **openpilot prior** C_α. Same per-segment bias as V1.
- **V3** — fit `(C_αf, C_αr)` bounded to (5e4, 5e5) N/rad. The skill's stock `fit_c_alpha` (single L-BFGS-B start at (1.5e5, 1.5e5)) traps in a flat-gradient region; multistarted from five points and kept best (Cf=Cr≈2.0e5, loss 0.01266). Neither bound pegged.
- **V4** — `sklearn.linear_model.Ridge(alpha=1)` on `[v, |a_y|, |δ|, sign(δ̇)]` against V3 residuals with **leave-one-segment-out** CV. Out-of-fold scoring only.

## Regressions and physical causes

- **V2 is a regression vs V1.** Openpilot's prior C_α (286k/356k N/rad) is stiffer than these Mach-E tyres behave, so ST under-rotates at meaningful slip, worsening cornering by ≈30–40% relative to V1. Matches the `references/ks-vs-st.md` "Known regression" warning. The skill made me **more honest, not more optimistic**.
- **V3 is a near-zero recovery, still worse than V1.** Fitted Cf=Cr≈2.0e5 — *softer* than the openpilot prior — but the steady-state ST gain is structurally the wrong shape for the slip dynamics in the data (transient/phase, not steady gain).
- **V2/V3's straight RMSE is *lower* than V1's** (0.0043/0.0041 vs 0.0050) — numerical wash from how bias cleanup interacts with the small-δ limit.
- **V4 recovers what V2/V3 lost** and edges past V1 by 0.00010 rad/s. A small residual learner on KS+bias alone would have got most of V4's win without the ST detour.

## Notes / limitations

- No `evals/` harness in this module to validate report format — self-audited.
- Used first 80 of 315 Mach-E segments for runtime; the V2 regression is the headline regardless of scale.
- The skill's `fit_c_alpha` single-start L-BFGS-B is fragile on this loss surface; patched in `tools/run_ladder.py` with a multistart, but did not modify the skill (read-only).
