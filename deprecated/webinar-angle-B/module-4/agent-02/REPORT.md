# Module-4 / agent-02 (angle-B) — Lateral fidelity ladder

**Platform scored:** `FORD_MUSTANG_MACH_E_MK1` (315 segments, 913 626 samples @ 50 Hz). Lightning has truth too but Mach-E has the larger set. Tesla excluded — no IMU truth channel.

**Clamped vs predicted:** `v_mps` and `delta_road_rad` are inputs (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). The channel under test is `yaw_rate_pred_rads`; truth is `yaw_rate_meas_rads`; residual `pred − meas`.

**Sign sanity:** `corr(δ_road, ψ̇_meas)` on cornering = **+0.702**. ISO 8855 intact.

**Regime mask** (fixed): straight `|δ|<0.01`; steady `|δ|≥0.01 ∧ |δ̇|<0.05`; transient `|δ|≥0.01 ∧ |δ̇|≥0.05`. Counts: 785 093 / 107 055 / 21 478.

## Variant ladder (locked V0 → V3, strict marginal accounting on all-regime RMSE)

| # | Variant | all RMSE | straight | steady | transient | Δ all | named drop |
|---|---|---|---|---|---|---|---|
| V0 | KS baseline (`yaw_rate_resid_rads` as-is) | 0.01613 | 0.00877 | 0.03172 | 0.05689 | — | — |
| V1 | + per-segment straight-line bias | 0.01469 | 0.00493 | 0.03167 | 0.05739 | **-0.00143** | seg-bias |
| V2 | linear-ST gain, prior C_α (Mach-E openpilot) | 0.01551 | 0.00339 | 0.03429 | 0.06287 | **+0.00082** | ST-prior (regression) |
| V3 | linear-ST, fit C_α | 0.01515 | 0.00411 | 0.03308 | 0.06082 | **-0.00036** | ST-refit |

**Accounting:** strict marginal, fixed V0→V3 order, all-regime RMSE. Total drop V0→V3 = -0.000972; sum of marginals = -0.000969; within 0.3% — well inside 15% tolerance. No double-counting.

**Fitted stiffnesses (V3):** C_αf = 187 584 N/rad (65% of prior), C_αr = 154 703 N/rad (43% of prior). Neither pegs the 50–500 kN/rad bounds.

## Honest regression flags

- **V2 is a regression on cornering** (+8% steady, +10% transient). Openpilot's prior C_α understeers the Mach-E *more* than KS does on these roads. The straight-line improvement at V2 comes from re-fitting the per-segment bias against a worse predictor; it should not be read as a model upgrade.
- **V3 recovers most but not all of the V2 cornering regression**: steady 0.03308 (V3) vs 0.03167 (V1); the refit ST never beats KS+bias on this dataset.
- **Headline credit:** V1 alone delivers ~146% of the eventual V0→V3 drop. The cheap fix wins.

## RPI artifacts

- Research: `rpi/runs/20260527-155834/research.md`
- Plan: `rpi/runs/20260527-155834/plan.md`
- Implement: `rpi/runs/20260527-155834/implement-notes.md`
- Code: `tools/eval_lateral.py`. Numeric output: `out/lateral_eval.json`.

## Painful absence

A non-linear tyre rung (V4 Pacejka) is needed to test whether the *form* of the linear-ST gain is wrong on transient steering — V3 still loses to V1 on transient cornering (0.0608 vs 0.0574). Out of scope at 15 min.

## Near-miss

V3 closes to within 0.0004 rad/s of V1 on all-regime — going from KS+bias to a 2-parameter fitted linear-ST model is statistically a wash on this data.

## Surprise

Fitted C_αr (155 kN/rad) is **43%** of the openpilot prior (356 kN/rad). Either the rear tyres slip far earlier than openpilot's canonical value claims, or — more likely — the linear-ST steady-state gain is absorbing model error it has no physical right to absorb. Treat the V3 stiffnesses as a calibration fudge, not a measurement.
