# REPORT — lateral-fidelity workflow (workshop scaffold S2)

## Platform and contract

- Platform scored: **FORD_MUSTANG_MACH_E_MK1** (Ford Mustang Mach-E MK1, 315 segments, 913 626 rows).
- `yaw_rate_meas_rads` is measured truth (rlog IMU, Ford-only). Residual under test: `yaw_rate_resid_rads = yaw_rate_pred − yaw_rate_meas`.
- Speed `v` and steering `δ` are **clamped to measured** under the speed-known operating contract (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). The lateral residual is the *only* metric. No "fix" via unclamping.
- Regime split (fixed thresholds): straight 785 093 rows, steady 106 978, transient 21 555.

## Variant ladder

| variant | overall | straight | steady | transient |
|---|---:|---:|---:|---:|
| V0 (baseline KS as-shipped) | 0.01613 | 0.00877 | 0.03173 | 0.05680 |
| V1 (KS recalib L + per-segment straight-row yaw-gyro bias) | **0.01469** | **0.00493** | 0.03168 | 0.05730 |
| V2 (Linear ST, openpilot prior Cα) | 0.01653 | 0.00701 | 0.03450 | 0.06234 |
| V3 (Linear ST, fit Cα, L-BFGS-B in (5e4, 5e5) N/rad) | 0.01663 | 0.00700 | 0.03482 | 0.06266 |

V3 fit returned C_α_f = C_α_r = 1.50e5 (= x0); not pegged at the upper bound, but L-BFGS-B did not move off the initialisation. Treated as a soft regression flag (see below).

## Attribution

Marginal drop in overall RMSE (negative = improvement, positive = regression):

- **V0 → V1: −0.00144 rad/s (−8.9 %).** Real improvement; concentrated almost entirely in the straight regime (−0.00384 rad/s, −43.8 %). Steady and transient essentially unchanged. Physical reading: this is a per-segment yaw-gyro DC offset, not a vehicle-dynamics correction.
- **V1 → V2: +0.00184 rad/s (regression).** Switching from KS to Linear ST with openpilot prior cornering stiffnesses degrades every regime. The understeer term `K_us · v²` over-softens predicted yaw at the speeds this dataset spends time in, given the prior Cα.
- **V2 → V3: +0.00010 rad/s (regression).** Negligible; the L-BFGS-B fit did not move off x0 = (1.5e5, 1.5e5). With v and δ clamped and yaw dominated by straight-line rows where Cα does little work, the loss is near-flat at init.
- **Sum of marginals vs. total V0 → V3:** −0.00144 + 0.00184 + 0.00010 = +0.00050 ≈ total V0→V3 (+0.00050). Within 15 %: yes (exact, by construction).

**Net conclusion: the ladder peaks at V1.** V2 and V3 do not earn their inclusion.

## Regressions and physical reasons

- **V2, V3 regress past V0 on overall and on every regime.** Cause: the Linear ST understeer correction with openpilot-canonical Cα reduces predicted yaw rate at moderate v, but the actual residual budget in this dataset is dominated by (a) yaw-gyro DC offset in straight rows and (b) genuine transient dynamics the linear model also can't capture. V2 makes the straight-rows worse (yaw under-prediction now competes with a residual bias V1 fixes and V2 does not). Recommendation if the ladder were extensible: apply V1's bias *before* V2's understeer term.
- **V3 fit did not converge.** Not pegged at the upper bound (so not the flag the workflow defines), but stuck at x0. Workflow does not allow restart with new seeds; flagged here.
- **Transient regime is barely touched by anything.** V0 = 0.0568, V1 = 0.0573, V2 = 0.0623, V3 = 0.0627. The workflow has no rung that targets transient dynamics (would want a residual learner — out of scope here).

## Notes

- **Tool patch required.** `tools/step4_run_st_upgrade.py` indexes `P["L"]` etc., but `PARAM_BY_PLATFORM["FORD_MUSTANG_MACH_E_MK1"]` returns a frozen dataclass (`MachEST`), not a dict. Patched in place with a dict-or-attribute fallback over (L, l_f, l_r, m, C_alpha_f, C_alpha_r). Step ordering and physics unchanged. Without the patch step 4 raises `TypeError: 'MachEST' object is not subscriptable`.
- **What the workflow disallows that I wanted.** (i) A V4 residual learner targeting the transient regime; (ii) restarting V3's L-BFGS-B from multiple seeds to escape the stuck x0. Both forbidden by AGENTS.md ("ladder stops at V3", "do not deviate"). Recorded, not executed.
- **Most painful absent component:** an **eval rung**. With per-segment, per-regime, held-out scoring I could attribute V1's gain to sensor bias vs. dynamics, and could distinguish V3's "fit failed" from "fit succeeded, model is wrong". Three-number-per-variant reporting is not enough to discharge the user's request to say "how much each change contributed".
