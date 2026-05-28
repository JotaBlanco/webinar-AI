# REPORT — webinar-angle-D / module-4 / agent-05

## Lateral-fidelity ladder on Ford Mustang Mach-E (MK1)

- **Platform.** `FORD_MUSTANG_MACH_E_MK1`. The truth channel `yaw_rate_meas_rads` is **measured** (Ford party DBC, IMU-decoded), not a model output.
- **Contract.** Speed-known, lateral-only. `v` (`v_mps`) and `δ` (`delta_road_rad`) are **clamped** to measured each step (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Speed-state agreement is zero by construction and not a metric.
- **Data.** 8 deterministically-picked Mach-E `sim.csv` segments under `data/sim/segments/FORD_MUSTANG_MACH_E_MK1/`. 23,190 rows total — regime split: straight=22,155, steady-cornering=639, transient-cornering=396. The set is straight-line-dominated; weight that when reading per-regime numbers.
- **Composition.** `regime-segmentation` v0.3 loaded and validated the CSVs and produced the `regime` column; `lateral-fidelity-triage` v0.5 consumed the tagged DataFrame, ran the V0→V4 ladder, and computed per-regime RMSE via `segment.per_regime_rmse`. Both skills share regime thresholds (`|δ|<0.01 rad` straight; `|dδ/dt|<0.05 rad/s` splits steady/transient).
- **Accounting.** Strict marginal, fixed order V0→V1→V2→V3→V4. Each marginal drop is `RMSE(V_{i-1}) − RMSE(V_i)` on the overall residual. Marginals sum to 0.006241; total drop is 0.006241 — well inside the 15% sanity band.
- **Sensor gate.** `python3 skills/lateral-fidelity-triage/sensor.py out/best_V2.csv` → both checks PASS. corr(pred, meas) on cornering = 0.999; RMSE(candidate) = 0.00911 ≤ V0 = 0.01545.

## Variant ladder (RMSE in rad/s; lower is better)

| Variant | Description | Overall | Straight | Steady-corner | Transient-corner | Marginal (overall) |
|---|---|---|---|---|---|---|
| V0 | baseline `yaw_rate_resid_rads` as-is | 0.01545 | 0.01386 | 0.03404 | 0.03688 | — |
| V1 | KS recal `(v/L) tan δ` + per-segment yaw-gyro bias on straights | 0.00932 | 0.00591 | 0.03083 | 0.04004 | **+0.00613** |
| V2 | Linear ST with prior Cα (PARAM_BY_PLATFORM) + per-seg bias | **0.00911** | **0.00292** | 0.03705 | 0.04657 | +0.00021 |
| V3 | Linear ST with fit Cα (L-BFGS-B, bounds 5e4–5e5) + per-seg bias | 0.00921 | 0.00310 | 0.03729 | 0.04680 | **−0.00010 (regression)** |
| V4 | V3 + Ridge residual learner LOO on `[v,|a_y|,|δ|,sign(δ̇)]` | 0.00921 | 0.00318 | 0.03716 | 0.04658 | +0.000006 (noise) |

- **Best variant.** V2 — picked on overall RMSE; written to `out/best_V2.csv`; sensor PASS.
- **V1 owns the win.** 98% of the total V0→V_last drop is V1 alone (recalibrated KS with the canonical `L` from `parameters.py`, plus a per-segment yaw-gyro bias subtracted on straight-line samples). The baseline `yaw_rate_resid_rads` column carries a per-segment DC offset that V1 removes.
- **V2's only contribution is on straights.** Going from KS to linear-ST drops straight RMSE 0.0059 → 0.0029 but worsens cornering (steady 0.0308 → 0.0370). Because straights dominate row count, V2 still wins overall — but anyone who cares about cornering specifically should prefer V1.
- **V3 regression, with a physical reason.** `fit_c_alpha` returned `Cαf = Cαr = 150,000 N/rad` — **exactly the L-BFGS-B initial guess (1.5e5, 1.5e5)**. `pegged_upper=False` per the skill's check, but the optimizer never moved. Cause: with 22,155 of 23,190 rows being straight-line (where the linear-ST gain is `v·δ/L` independent of Cα), the loss surface in the cornering window doesn't dominate. The "fit" is degenerate. V3 ≈ V2 with a hair more noise from re-running `per_segment_bias` on identical predictions; report as regression per v0.5 rule.
- **V4 ships as no-op.** Ridge LOO on top of V3 moved overall RMSE by 6e-6 rad/s — within numerical noise. Per skill rule "if V4 doesn't beat V3 out-of-fold, ship V3 and call V4 a regression", V4 is not shippable; we keep V2 as best.

## Per-change attribution

- **KS recal + yaw-gyro bias on straights (V1)** — Δ = 0.00613 rad/s overall (98% of total improvement). Almost entirely on straights (0.01386 → 0.00591); some degradation on transient cornering (0.03688 → 0.04004), because the per-segment DC bias is computed on straights and doesn't capture cornering-only offsets.
- **Linear-ST prior Cα (V2)** — Δ = 0.00021 rad/s overall, but +0.00299 on straights and **regression** on cornering. The understeer gradient `K_us` with prior Cα reduces predicted yaw at high speed, which is right for straights, wrong for the cornering regime in this segment set.
- **Linear-ST fit Cα (V3)** — Δ = −0.00010 (regression). Optimizer never left `x0`. Fit is unidentifiable on a straight-dominated set.
- **Ridge LOO residual learner (V4)** — Δ = +6e-6 (noise). Features `[v,|a_y|,|δ|,sign(δ̇)]` do not generalise across segments at this signal level.

## Components present / absent

- Present: AGENTS.md (thin); `skills/lateral-fidelity-triage/SKILL.md` v0.5 with `triage.py` and `sensor.py`; `skills/regime-segmentation/SKILL.md` v0.3 with `segment.py`; `tools/run_ladder.py` composition harness.
- Absent: no `evals/`, no held-out test segment set, no plotting/visualisation skill, no reference of measured `a_lat_meas_mps2` as a secondary metric (only `yaw_rate_meas_rads` exercised).

## Limitations and isolation

- Read only the agent-05 module, `code/` symlink, and `data/` symlink. Did not consult sibling agents, other angles, `_shared`, `_launch`, F1, or `raw-model/`.
- Segment selection was deterministic (first 8 sorted Mach-E `sim.csv` paths). No held-out generalisation check beyond V4's per-segment LOO.
- The cornering subset is small (1,035 rows out of 23,190). Per-regime RMSE on steady/transient is statistically thin; treat the 4th-decimal differences with caution.
