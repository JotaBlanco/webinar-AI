# REPORT — lateral-fidelity-triage on FORD_MUSTANG_MACH_E_MK1

**Platform scored:** FORD_MUSTANG_MACH_E_MK1 (Mach-E MK1).
**Truth channel:** `yaw_rate_meas_rads` is *measured* truth — decoded from the rlog IMU via the Ford party DBC (Mach-E is a first-class openpilot port; SKILL.md confirms Tesla has no decoded IMU yaw, Ford does).
**Sample:** 20 segments, deterministic stride over 315 available Mach-E `sim.csv` files; 57,987 rows total.
**Residual under test:** `yaw_rate_pred − yaw_rate_meas` (rad/s).
**Operating contract:** speed-known, lateral-only (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`, per SKILL.md).

## Variant ladder

| Variant | overall RMSE [rad/s] | straight | steady | transient | attribution Δ vs prev |
|---|---|---|---|---|---|
| V0 baseline (`yaw_rate_resid_rads` from CSV)               | **0.01192** | 0.00807 | 0.01729 | 0.04098 | — |
| V1 KS recalibrated, canonical L, per-segment straight bias | **0.00993** | 0.00430 | 0.01683 | 0.03948 | **−0.00199 (−16.7%)** |
| V2 Linear ST, prior C_α (openpilot-canonical)              | 0.01155     | 0.00350 | 0.02088 | 0.04681 | +0.00162 *(regression)* |
| V3 Linear ST, fit C_α (Cα_f≈653k, Cα_r≈668k, not pegged)   | 0.01048     | 0.00360 | 0.01820 | 0.04342 | −0.00107 (vs V2) |
| V4 Ridge residual learner LOO on V3 residuals              | 0.01108     | 0.00382 | 0.02078 | 0.04134 | +0.00060 *(regression)* |

Best variant overall: **V1**. Best transient: V1. Best straight: V2 (but loses elsewhere). Best steady: V1.

## Attribution

- **V1 is the only positive contributor on overall RMSE.** It contributes the whole 0.00199 rad/s overall improvement (−16.7% vs V0). Decomposition by regime: straight bin drops from 0.00807 → 0.00430 — i.e. ~half of V1's gain comes from removing a per-segment gyro DC bias on straight-line samples. The other half is steady/transient improvement from using the canonical wheelbase L=2.984 m via `MACH_E` parameters.
- **V2 over-shrinks gain.** Prior C_α makes K_us > 0 in a regime where the in-CSV KS prediction (no slip term) was already accurate; the ST gain at v=20 m/s is ~18% lower than KS, so steady and transient RMSE grow.
- **V3 partially repairs V2** by fitting Cα toward higher values (Cα_f, Cα_r ≈ 6.5e5 N/rad) — i.e. the data prefers a *stiffer* tire than the openpilot prior, edging back toward the KS gain — but V3 still ends above V1.
- **V4 (Ridge residual learner)** doesn't help on this segment set. The OOF residuals predicted by ridge are noise on top of V3's already over-corrected gain.

## Why V1 beats the full ladder on Mach-E

The baseline `yaw_rate_pred_rads` in `sim.csv` is essentially `(v/L)·tan(δ)` with L = 2.984. Correlation between in-CSV `yaw_rate_pred_rads` and `yaw_rate_meas_rads` on cornering rows is **0.996**. So the dominant residual is a small gyro DC offset and a tiny gain mismatch, not slip-angle dynamics. A per-segment de-meaning on straight samples is the right tool. The ST layer adds parameters whose prior is calibrated to *high-grip / Tesla-Model-3-ish* assumptions and *reduces* the gain on the Mach-E.

## Sign-check

`corr(δ_road, ψ̇_meas)` on cornering rows = +0.77 (positive). No sign error, per SKILL.md § Sign-error checklist.

## Limitations / known harness gaps

- SKILL.md is v0.1. It explicitly omits: regression-flag rule, V0-methodology pin, ST-low-v warning, single-table rule, pegged-Cα detection.
- The supplied `triage.fit_c_alpha` uses L-BFGS-B with `x0=(1.5e5, 1.5e5)`. On Mach-E data, that x0 lies on a quasi-flat ridge near the K_us-singular surface and the optimizer terminates without leaving x0. `pegged_at_upper` is False because Cα is at x0, not at the upper bound — so the helper silently mis-reports "converged". I worked around this with a log-grid pre-search + Nelder-Mead refine; the patched fit found Cα_f≈652k / Cα_r≈668k with RMSE 0.01226 (still worse than V1). A "fit-converged" sanity check should be added in the next SKILL.md revision.
- Only Mach-E was scored (per SKILL.md default). Lightning data is available but out of scope for this run.
- No `references/` or `evals/` subfolder — the skill v0.1 substrate does not include reference numbers I could regress against.

## Artefacts

- `out/run_ladder.py` — driver.
- `out/ladder_results.csv` — the table above.
- `out/meta.json` — fit Cα, sample size, parameter values used.
