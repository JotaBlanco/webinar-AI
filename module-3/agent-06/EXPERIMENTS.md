# EXPERIMENTS log — agent-06

Pooled KPIs across all 4 platforms (1996 segments, ~5.2M samples). Tesla is V0 passthrough.

## V0 — baseline KS passthrough
- Rung: 0
- Hypothesis: floor.
- Result: yaw_rate_rmse = 0.012934 rad/s, cte_rmse = 163.83 m.

## V1 — KS + understeer + lag + per-segment δ₀ (recipe defaults from anti-patterns.md)
- Rung: 0
- Hypothesis: replicate the "legal cousin" recipe with platform-gated per-segment δ₀ (Mach-E + IONIQ-5 on, Lightning off).
- Change: linear understeer (g, L_eff, K_us) + first-order lag (tau), with per-segment δ₀ estimated from the V0 straight-row gate `|yaw_v0|<0.03 ∧ v>5`.
- Result: yaw = 0.005874 rad/s (−54.6% vs V0), cte = 56.81 m (−65.3% vs V0).
- Notes: Mach-E shows residual signed yaw bias (−0.00142 rad/s) → cte_drift −22.0 m. Worst-CTE segments concentrate on 5 Mach-E segments under route 33439c2a9c.

## V2 — Nelder-Mead refit with L_eff pinned to physical wheelbase
- Rung: 0
- Hypothesis: pinning L_eff would resolve the g↔L_eff scale invariance and let scipy find a tighter fit per platform.
- Change: scipy NM over (g, K_us, tau, δ₀_fallback) on 100 training segments per platform; yaw-RMSE + 50×|bias| loss.
- Result: yaw = 0.007650 rad/s, cte = 69.23 m — WORSE than V1.
- Reason: Mach-E pegged at upper g bound (1.30) and lower tau bound (0.005). The recipe value L_eff=2.22 for Mach-E is FAR below the physical 2.984 m wheelbase — the recipe encodes an effective-wheelbase choice that fixed-L_eff fitting cannot reach. Pinning L_eff to the physical value is NOT a free move.
- Decision: revert to V1 defaults.

## V3 — coefficient sweep on Mach-E only (g ∈ [0.870, 0.920], K_us ∈ [0.0010, 0.0020])
- Rung: 0
- Hypothesis: the published Mach-E coefficients are already near optimum; sweeps will be flat.
- Result: best Mach-E-only yaw = 0.00842 (g=0.891, K_us=0.0020) — virtually identical to V1 default 0.00859. The signed yaw bias (−0.0014) is invariant to (g, K_us) within ±2% — likely a structural artefact (lag asymmetry between L/R turns, or missing nonlinear tyre), reachable only by climbing a rung.
- Decision: ship V1 defaults.

## V4 — Rung-1 attempt: linear dynamic single-track with slip angles
- Rung: 1
- Hypothesis: replace kinematic steady-state with a slip-angle linear bicycle (vy, r) state-space; backward-Euler integration should out-perform the kinematic understeer model in the transient regime (rung-0 yaw_rmse peaks at 0.0165 rad/s there).
- Change: 2-state semi-implicit (backward Euler) integration of
    m·v̇_y = −C_f·α_f − C_r·α_r − m·u·r
    Iz·ṙ   = −l_f·C_f·α_f + l_r·C_r·α_r
  with openpilot-canonical mass / inertia / tyre stiffness from `code/parameters.py` for Mach-E and Lightning; IONIQ-5 used literature defaults (m=2100, Iz=4500, Cf=300k, Cr=370k). Per-segment δ₀ kept on for Mach-E + IONIQ-5.
- Result: yaw = 0.008636 rad/s (vs V1 0.005874 — WORSE by +47%), cte = 69.51 m (vs V1 56.81 — WORSE by +22%).
- Per-platform: Mach-E yaw=0.01379, Lightning yaw=0.00914, IONIQ yaw=0.01071. Lightning fares closest to V1; Mach-E worst.
- Failure notes: first explicit-Euler attempt blew up (stiffness with C_f≈300k at 20 ms — eigenvalues outside stability region). Backward Euler stabilises but the openpilot C_f/C_r priors are too high for these data — the linear-ST steady-state K_us = (m/L²)(l_r/C_f − l_f/C_r) is *smaller* than what the rung-0 fit converged on. Rung 1 needs a joint refit of (C_f, C_r) per platform to be competitive — out of budget here.
- Reason for falling back to rung-0: yaw_rmse increased on all three live platforms.

## Shipped — V1 (rung 0)
- Coefficients in `final-model/coeffs.json`.
- Final pooled: yaw_rate_rmse = 0.005874 rad/s (−54.6% vs V0), cte_rmse = 56.81 m (−65.3% vs V0).
