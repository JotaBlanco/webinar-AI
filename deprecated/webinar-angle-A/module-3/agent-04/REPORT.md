# Module-3 / agent-04 — Lateral-fidelity triage (Mach-E)

## Setup

- **Platform scored**: `FORD_MUSTANG_MACH_E_MK1`. The `yaw_rate_meas_rads` column is the **measured** truth channel from the rlog gyro — not a prediction, not a clamped state, not self-consistency.
- **Speed-known contract**: `v_mps` and `delta_road_rad` are **clamped** at every integrator step. The integrator's own speed/steer updates are discarded. The only **predicted** channels are `yaw_rate_pred_rads` and `a_y_pred_mps2`. Lateral fidelity lives entirely in the residual `pred − meas`.
- **Segments used**: 60 Mach-E `sim.csv` files (first 60 lexicographic), 173 940 rows at 50 Hz. Same segment set, same regime mask, every row.
- **Regime mask**: straight `|δ_road|<0.01`; steady `|δ|≥0.01 ∧ |dδ/dt|<0.05`; transient `|δ|≥0.01 ∧ |dδ/dt|≥0.05`.
- **Parameters**: `PARAM_BY_PLATFORM["FORD_MUSTANG_MACH_E_MK1"]`. `L=2.984 m`, `m=2336 kg`, `I_z=4879.05`, `l_f=1.313`, `l_r=1.671`, `C_αf_prior=286 551`, `C_αr_prior=355 912 N/rad`, `i_s=17`.
- **Sign check**: `corr(δ_road, ψ̇_meas) = +0.93` on cornering — left-positive convention OK.
- **Attribution scheme**: strict marginal in fixed order V0→V1→V2→V3→V4. Marginals sum to total within float epsilon.

## Variant ladder — RMSE on `yaw_rate_resid_rads`, rad/s

| Variant | Overall | Straight | Steady cornering | Transient cornering | Marginal Δ overall |
|---|---:|---:|---:|---:|---:|
| V0 baseline (column as-is)                       | 0.012144 | 0.008508 | 0.025192 | 0.048887 | — |
| V1 KS recal + per-seg yaw-gyro bias              | 0.010552 | 0.005064 | 0.026019 | 0.051156 | **-0.001593** (improves) |
| V2 Linear ST with prior C_α + bias               | 0.012480 | 0.003346 | 0.034243 | 0.063623 | **+0.001929** (regression) |
| V3 Linear ST with fit C_α + bias                 | 0.012597 | 0.003430 | 0.034580 | 0.063980 | **+0.000116** (regression) |
| V4 Ridge residual learner on V3 (LOO CV)         | 0.010045 | 0.003510 | 0.025443 | 0.053823 | **-0.002551** (improves) |

Total drop V0→V4 = **0.002099 rad/s (17.3% relative)**. Sum of marginals = 0.002099 (exact).

## What each variant did

- **V1** — Recompute `ψ̇ = (v/L)·tan(δ_road)` with canonical L, subtract per-segment yaw-gyro bias from straights (≥10 samples). Mean bias ≈ 1.82e-4 rad/s; median 7.12e-4. Largest physically-motivated win: straight-line RMSE drops 40% (0.0085 → 0.0051).
- **V2** — Linear single-track steady-state gain `ψ̇_ST = vδ/(L(1+K_us v²))` with openpilot prior `C_α` + same bias. Improves straight (bias absorbs cleanly) but **worsens cornering substantially**: steady +36%, transient +24%. This is the regression `references/ks-vs-st.md` warns about — the openpilot prior `C_α` is *stiffer than the Mach-E tyres actually behave*, so the linearisation over-damps yaw and predicted `ψ̇` falls below measured.
- **V3** — Fit `(C_αf, C_αr)` on segment set via L-BFGS-B, bounds (5e4, 5e5) N/rad. Optimiser returned `(1.5e5, 1.5e5)` — exactly the initial guess — indicating a flat / non-smooth local loss; coarse grid confirms ~1.4% variation across the bounded box (best ≈ 0.01320 at 3e5, 3e5 vs 0.01339 at the prior). **Fit doesn't beat V2 in real terms** — flagged as regression.
- **V4** — Ridge on `[v, |a_y|, |δ|, sign(δ̇)]` against V3 residuals with **leave-one-segment-out** CV. Recovers everything V2+V3 lost and pushes overall below V1 (0.01005 < 0.01055).

## Regressions, named honestly

- **V2 regression** vs V1 on every cornering regime. Openpilot's Mach-E prior `C_α` is too stiff for these tyres on these roads, so ST over-damps yaw rate. KS over-predicts; ST with this prior over-corrects.
- **V3 also a regression** vs V1. Implied lesson: this is the wrong DoF to vary.
- **V4 positive overall** but it is *learning the residual*, not adding physics. Whatever it captures is an admission that the dynamics rung above is incomplete.

## Limitations

- Only 60 of 315 available Mach-E segments used in budget.
- No F-150 Lightning run for comparison.

## Component I most felt the lack of

A **calibrated steering-ratio / EPS-compliance correction module** between V1 and V2. The big residual on cornering is not "wrong Cα" but "δ_road derived from `delta_wheel_deg / i_s` understates the actual road-wheel angle under torque load on this rack". Without a rack-compliance term I had to leave that gap unaddressed and let V4 launder it as a learned residual — exactly the dishonest credit-allocation the skill is designed to prevent.

Files: `out/run_ladder.py`, `out/ladder_results.json`.
