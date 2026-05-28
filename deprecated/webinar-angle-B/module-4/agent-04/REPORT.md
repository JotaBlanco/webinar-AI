# Module-4 / agent-04 (angle-B) — Lateral fidelity ladder

**Headline.** On FORD_MUSTANG_MACH_E_MK1 (315 segments, 913 626 samples, 50 Hz, clamped `v` + `δ`; predicting `yaw_rate_pred_rads` against `yaw_rate_meas_rads`), the locked V0→V4 ladder reduced overall yaw-rate-residual RMSE from **0.01613 → 0.01533 rad/s (-4.96%)**. The ladder spent more attribution surface on rejecting hypotheses than on closing the gap — the honest result is that linear-ST steady-state + first-order lag is at its ceiling for this dataset.

**Operating contract.** `v_mps` and `delta_road_rad` are **clamped to measured**; `yaw_rate_pred_rads` and `a_y_pred_mps2` are the **predicted** channels under test. Residual: `yaw_rate_resid_rads = yaw_rate_pred_rads − yaw_rate_meas_rads`. Sign sanity OK (`corr(δ, ψ̇_meas) = +0.702` on cornering).

## Variants (strict marginal V_prev→V_this on overall RMSE)

Same mask: straight `|δ|<0.01`, steady `|δ|≥0.01 ∧ |dδ/dt|<0.05`, transient `|δ|≥0.01 ∧ |dδ/dt|≥0.05`.

| # | Variant | Straight | Steady | Transient | Overall | Marginal drop | Flag |
|---|---------|----------|--------|-----------|---------|---------------|------|
| V0 | KS as-is | 0.00877 | 0.03177 | 0.05677 | 0.01613 | — | baseline |
| V1 | Per-segment gyro DC (straight-only estimator) | 0.01531 | 0.03283 | 0.05694 | 0.02010 | +0.00397 (+24.6%) | **REGRESSION** (plan-anticipated) |
| V2 | Linear ST steady-state, prior C_α | 0.00339 | 0.03432 | 0.06272 | 0.01550 | -0.00460 (-22.9%) | steady+transient regress vs V0 |
| V3 | Fit C_α (bounded 50–500 kN/rad) | 0.00339 | 0.03432 | 0.06272 | 0.01550 | 0 (0.0%) | **NEAR-MISS** (fit → priors) |
| V4 | First-order lag τ=0.08 s | 0.00314 | 0.03457 | 0.06066 | 0.01533 | -0.00017 (-1.1%) | small transient gain |

Marginal drops sum to V0→V4 total by construction.

## Painful absence

Nothing in the ladder addresses the **two-state ST dynamic eigenmodes** that the transient regime needs. Transient RMSE *grows* from V0 (0.0568) to V2 (0.0627) because steady-state ST over-predicts understeer for the actual Mach-E response, and our first-order lag (V4) can recover only 3% of that. Pacejka / dynamic-ST were out of scope.

## Near-misses

- V3 L-BFGS-B fit returned the openpilot priors *exactly* — the cornering loss surface is locally flat at the priors because residual is transient-dominated, not gain-dominated.
- V1 hypothesis rejected by its own falsification criterion: straight RMSE *rose* (0.00877 → 0.01531), proving per-segment gyro DC offset is not the dominant straight-line failure mode here.

## Surprises

1. Linear ST with openpilot-canonical priors makes cornering *worse* than KS on Mach-E — production prior assumes more understeer than the on-road data shows.
2. V3 fit declined to move from the priors at all (not pegged) — strong evidence the residual lives in dynamics, not stiffness.
3. F-150 `a_lat_meas_mps2` has `max|a_y|=1057 m/s²` — units/outlier defect; reason scored Mach-E only.
4. `parameters.py` F-150 values disagree with the skill's stated F-150 numbers — dict-vs-skill discrepancy worth reconciling.

## RPI artifacts

- Research: `rpi/runs/20260527-155843/research.md`
- Plan (locked): `rpi/runs/20260527-155843/plan.md`
- Implement notes: `rpi/runs/20260527-155843/implement-notes.md`
- Numerics: `out/ladder.json`
- Tools: `tools/research_baseline.py`, `tools/run_ladder.py`
